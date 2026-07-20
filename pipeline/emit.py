"""Pass 2 — resolve embeds, write page bundles, prune withdrawn output.

Every published note becomes a Hugo leaf bundle:

    content/<slug>/index.md
    content/<slug>/diagram.png

Bundles are used uniformly, even for text-only notes. The URL is identical
either way, and uniformity avoids a stale-file class of bug: a note that gains
an image later would otherwise need its old flat file deleted.

v0 still does NOT resolve wikilinks between notes — those are flattened to
plain text. Assets, however, now resolve and copy.

A note on the leak rule
-----------------------
An earlier formulation ("no unpublished title may appear in any output") is
too broad to enforce, because an author may legitimately write a private
note's title in their own prose. The workable distinction is:

  * AUTHOR-WRITTEN BODY TEXT — the author wrote `[[Personal Kanban]]` in a note
    they chose to publish. Rendering those words is their call. The pipeline
    must not *link* it, and it warns so the author can reconsider.

  * PIPELINE-GENERATED SURFACES — backlinks, indexes, graph views, related
    notes. These introduce titles the author never chose to put on that page.
    Here the rule is absolute and asserted.

v0 only produces author-written body text, so it warns. The assertion lands in
v1 alongside the backlink index.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .registry import ASSET_SUFFIXES, Note, Registry, slugify

# Fenced blocks and inline code are masked before wikilink matching, so
# `[[this]]` inside a code sample survives untouched (PRODUCT.md §7.6).
CODE_FENCE_RE = re.compile(r"^```.*?^```|^~~~.*?^~~~", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]\n|]+)(?:\|([^\]\n]*))?\]\]")

# Obsidian sizing syntax: ![[img.png|400]] or ![[img.png|400x300]]
SIZE_RE = re.compile(r"^\d+(x\d+)?$")

# A blockquote line left empty once its embed was removed.
EMPTY_QUOTE_RE = re.compile(r"^>[ \t]*$\n?", re.MULTILINE)

_PLACEHOLDER = "\x00MASK{}\x00"


@dataclass
class LinkRef:
    source: str
    target: str
    display: str
    is_embed: bool
    status: str          # "published" | "unpublished" | "dangling"


@dataclass
class AssetRef:
    source: str          # slug of the note embedding it
    target: str          # filename as written in the vault
    dest: str | None     # filename as written into the bundle
    status: str          # "copied" | "missing"


@dataclass
class EmitResult:
    written: list[str] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)
    assets: list[AssetRef] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    manifest: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------


def _mask(text: str) -> tuple[str, list[str]]:
    stash: list[str] = []

    def grab(match: re.Match) -> str:
        stash.append(match.group(0))
        return _PLACEHOLDER.format(len(stash) - 1)

    text = CODE_FENCE_RE.sub(grab, text)
    text = INLINE_CODE_RE.sub(grab, text)
    return text, stash


def _unmask(text: str, stash: list[str]) -> str:
    for i, original in enumerate(stash):
        text = text.replace(_PLACEHOLDER.format(i), original)
    return text


def asset_dest_name(source: Path, taken: set[str]) -> str:
    """Slugify an asset filename for the bundle, de-duplicating collisions.

    Vault filenames routinely contain spaces and mixed case; bundle filenames
    should not.
    """
    stem = slugify(source.stem) or "asset"
    suffix = source.suffix.lower()
    name = f"{stem}{suffix}"
    counter = 2
    while name in taken:
        name = f"{stem}-{counter}{suffix}"
        counter += 1
    taken.add(name)
    return name


# --------------------------------------------------------------------------
# Transform
# --------------------------------------------------------------------------


def transform(note: Note, registry: Registry) -> tuple[str, list[LinkRef], list[AssetRef], dict[str, Path]]:
    """Resolve embeds and flatten wikilinks.

    Returns (body, link refs, asset refs, {dest filename: source path}).
    """
    body, stash = _mask(note.body)
    links: list[LinkRef] = []
    assets: list[AssetRef] = []
    to_copy: dict[str, Path] = {}
    taken: set[str] = set()

    def replace(match: re.Match) -> str:
        bang, target, display = match.group(1), match.group(2), match.group(3)
        target = target.strip()
        base = target.split("#", 1)[0].strip()
        display = (display or "").strip()

        if Path(base).suffix.lower() in ASSET_SUFFIXES:
            source = registry.find_asset(base)
            if source is None:
                assets.append(AssetRef(note.slug, base, None, "missing"))
                return ""
            dest = asset_dest_name(source, taken)
            to_copy[dest] = source
            assets.append(AssetRef(note.slug, base, dest, "copied"))
            # A numeric "display" is Obsidian's width, not alt text. Width is
            # dropped for now — expressing it needs raw HTML, which needs
            # goldmark.renderer.unsafe (PRODUCT.md §13).
            alt = "" if (not display or SIZE_RE.match(display)) else display
            return f"![{alt}]({dest})"

        shown = display or base
        hit = registry.lookup(base)
        status = "dangling" if hit is None else ("published" if hit.published else "unpublished")
        links.append(LinkRef(note.slug, base, shown, bool(bang), status))
        return shown  # v0: plain text, no linking

    body = WIKILINK_RE.sub(replace, body)

    # Removing an embed that sat inside a blockquote leaves a bare "> " line.
    body = EMPTY_QUOTE_RE.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    return _unmask(body, stash), links, assets, to_copy


def build_frontmatter(note: Note, config: dict) -> dict:
    defaults = config.get("defaults", {})
    meta = note.meta

    out = {
        "title": note.title,
        "slug": note.slug,
        "type": meta.get("note_type") or defaults.get("type", "note"),
        "temporality": meta.get("temporality"),
        "growth": meta.get("growth") or defaults.get("growth", "seedling"),
        "draft": False,
    }

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if tags:
        out["tags"] = [str(t) for t in tags]

    # TODO: once `stamp` exists, `id` becomes the canonical URL and the slug
    # (plus every historical slug) becomes an alias — PRODUCT.md §12.1.
    if meta.get("id"):
        out["id"] = meta["id"]

    stamp = datetime.fromtimestamp(note.path.stat().st_mtime, tz=timezone.utc).isoformat()
    if out["temporality"] == "dated":
        out["date"] = meta.get("date") or stamp
    else:
        out["lastmod"] = meta.get("lastmod") or stamp

    return {k: v for k, v in out.items() if v is not None}


# --------------------------------------------------------------------------
# Emit
# --------------------------------------------------------------------------


def emit(registry: Registry, config: dict, repo_root: Path, apply: bool,
         previous_manifest: list[str] | None = None) -> EmitResult:
    result = EmitResult()
    content_dir = repo_root / config["content_dir"]

    for note in registry.published:
        if not note.slug:
            result.skipped.append((note.rel, "title produced an empty slug"))
            continue

        body, links, assets, to_copy = transform(note, registry)
        result.links.extend(links)
        result.assets.extend(assets)

        front = build_frontmatter(note, config)
        rendered = (
            "---\n"
            + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            + "---\n\n"
            + body.lstrip("\n")
        )

        bundle = content_dir / note.slug
        index_path = bundle / "index.md"
        result.manifest.append(str(index_path.relative_to(repo_root)))
        result.written.append(str(index_path.relative_to(repo_root)))

        for dest_name in to_copy:
            result.manifest.append(str((bundle / dest_name).relative_to(repo_root)))

        if apply:
            bundle.mkdir(parents=True, exist_ok=True)
            # Idempotency: only write when content changed, so commits show
            # what moved rather than touching every file (PRODUCT.md §7.6).
            if not index_path.exists() or index_path.read_text(encoding="utf-8") != rendered:
                index_path.write_text(rendered, encoding="utf-8")
            for dest_name, source in to_copy.items():
                dest_path = bundle / dest_name
                if not dest_path.exists() or dest_path.stat().st_size != source.stat().st_size:
                    shutil.copy2(source, dest_path)

    # ---- prune -----------------------------------------------------------
    # Only files this pipeline previously generated are eligible. Anything
    # authored directly in the repo (`source: repo`, PRODUCT.md §9.2) is never
    # in the manifest and is therefore never touched.
    #
    # This matters for withdrawal: setting `publish: false` must remove the
    # page from the site, not merely stop updating it.
    if previous_manifest:
        current = set(result.manifest)
        for rel in previous_manifest:
            if rel in current:
                continue
            stale = repo_root / rel
            # Guard: never delete outside content/.
            if content_dir not in stale.parents:
                continue
            result.pruned.append(rel)
            if apply and stale.exists():
                stale.unlink()

        if apply:
            for bundle_dir in sorted(content_dir.glob("*")):
                if bundle_dir.is_dir() and not any(bundle_dir.iterdir()):
                    bundle_dir.rmdir()

    return result
