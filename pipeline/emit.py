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

import html
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .ids import is_valid
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

# A Claude-generated interactive, referenced from a note by a fenced block:
#     ```artifact
#     src: thing.html
#     height: 600
#     ```
# The block keeps the note portable markdown — no raw HTML pins it to one
# renderer. The pipeline copies the .html into the bundle and swaps the fence
# for an iframe, which isolates the interactive's styles and scripts from the
# page (PRODUCT.md §9.1, §330). The emitted iframe is raw HTML, so it needs
# goldmark.renderer.unsafe, which hugo.toml enables (PRODUCT.md §13, §500).
ARTIFACT_FENCE_RE = re.compile(
    r"^```artifact[ \t]*\n(?P<inner>.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
ARTIFACT_FIELD_RE = re.compile(r"^[ \t]*(\w+)[ \t]*:[ \t]*(.+?)[ \t]*$", re.MULTILINE)

_PLACEHOLDER = "\x00MASK{}\x00"


@dataclass
class LinkRef:
    source: str
    target: str
    display: str
    is_embed: bool
    status: str          # "published" | "unpublished" | "dangling" | "source"
    target_id: str | None = None   # permanent id, when the target is published
    target_url: str | None = None


@dataclass
class AssetRef:
    source: str          # slug of the note embedding it
    target: str          # filename as written in the vault
    dest: str | None     # filename as written into the bundle
    status: str          # "copied" | "missing"


@dataclass
class PresentationRef:
    slug: str
    note_id: str
    mode: str            # "style" | "body"
    files: list[str]


@dataclass
class EmitResult:
    written: list[str] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)
    assets: list[AssetRef] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    manifest: list[str] = field(default_factory=list)
    unstamped: list[str] = field(default_factory=list)
    presented: list[PresentationRef] = field(default_factory=list)
    presentation_missing: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------


SOURCE_REPO_RE = re.compile(r"^source:\s*[\"']?repo[\"']?\s*$", re.MULTILINE)


def is_repo_authored(path: Path) -> bool:
    """True for a page written directly in the repo, not exported from the vault.

    Art-directed stories live in content/ but have no vault original, so the
    pruner would otherwise treat them as output that's no longer produced and
    delete them. `source: repo` in the frontmatter is the marker.

    Read textually rather than by parsing YAML: this runs against files the
    pipeline did not write, whose frontmatter it does not control.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return False
    return bool(SOURCE_REPO_RE.search(head))


def prune_orphans(content_dir: Path, manifest: set[str], repo_root: Path,
                  apply: bool) -> tuple[list[str], list[str]]:
    """Sweep content/ for files no manifest claims.

    Belt to the manifest's braces: catches output left by an older version of
    the pipeline, whose paths were never recorded.
    """
    removed, kept = [], []
    for path in sorted(content_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(repo_root))
        if rel in manifest:
            continue
        if path.suffix == ".md" and is_repo_authored(path):
            kept.append(rel)
            continue
        # An asset sitting beside a repo-authored index.md belongs to it.
        sibling = path.parent / "index.md"
        if path.suffix != ".md" and sibling.exists() and is_repo_authored(sibling):
            kept.append(rel)
            continue
        removed.append(rel)
        if apply:
            path.unlink()
    return removed, kept


class LeakError(Exception):
    """A pipeline-generated surface referenced an unpublished note."""


RELREF_RE = re.compile(r"""\{\{<\s*relref\s+["']([^"']+)["']\s*>\}\}""")
ID_LINK_RE = re.compile(r"\]\(/([a-z0-9]{10})/\)")
FRONT_ID_RE = re.compile(r"^id:\s*[\"']?([a-z0-9]{10})[\"']?\s*$", re.MULTILINE)
FRONT_TITLE_RE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.MULTILINE)
FRONT_TYPE_RE = re.compile(r"^type:\s*[\"']?(\w+)[\"']?\s*$", re.MULTILINE)


def ingest_repo_pages(content_dir: Path, graph: dict) -> list[str]:
    """Add repo-authored pages to the graph, with their outbound links.

    These pages never pass through the registry — they have no vault original —
    so without this they're invisible to the graph. An essay that links to three
    notes would produce no backlinks on any of them, which is exactly wrong: the
    essay is the most link-rich thing on the site.

    Their links are `relref` shortcodes or direct /<id>/ hrefs rather than
    wikilinks, so they need their own parser.

    Returns the titles added, so the leak assertion can allow them.
    """
    # dirname → id, across every page, so a relref target resolves to an id.
    dir_to_id: dict[str, str] = {}
    for index in content_dir.glob("*/index.md"):
        text = index.read_text(encoding="utf-8", errors="replace")
        found = FRONT_ID_RE.search(text)
        if found:
            dir_to_id[index.parent.name] = found.group(1)

    added: list[str] = []
    for index in sorted(content_dir.glob("*/index.md")):
        if not is_repo_authored(index):
            continue
        text = index.read_text(encoding="utf-8", errors="replace")
        found = FRONT_ID_RE.search(text)
        if not found:
            # No id means no permanent URL and no place in the graph. Reported
            # by export so it can be fixed rather than silently dropped.
            continue
        page_id = found.group(1)

        title = FRONT_TITLE_RE.search(text)
        page_type = FRONT_TYPE_RE.search(text)
        graph.setdefault(page_id, {
            "url": f"/{page_id}/",
            "title": title.group(1).strip() if title else index.parent.name,
            "type": page_type.group(1) if page_type else "essay",
            "outbound": [],
            "inbound": [],
        })
        added.append(graph[page_id]["title"])

        targets = {dir_to_id.get(m) for m in RELREF_RE.findall(text)}
        targets |= set(ID_LINK_RE.findall(text))
        for target in targets:
            if not target or target == page_id or target not in graph:
                continue
            if target not in graph[page_id]["outbound"]:
                graph[page_id]["outbound"].append(target)
            if page_id not in graph[target]["inbound"]:
                graph[target]["inbound"].append(page_id)

    return added


def build_graph(registry: Registry, links: list[LinkRef],
                content_dir: Path | None = None) -> dict:
    """The link graph, restricted to published notes.

    NODES ARE PUBLISHED NOTES ONLY, and edges only run between them. This is
    the surface PRODUCT.md §7.4 calls absolute: backlinks and graph views
    introduce titles the author never chose to put on a given page, so an
    unpublished note must not appear even as a label.

    Keyed by permanent id, not slug — the graph outlives any rename.
    """
    by_id: dict[str, Note] = {}
    for note in registry.published:
        raw = note.meta.get("id")
        if is_valid(raw):
            by_id[str(raw).strip()] = note

    slug_to_id = {n.slug: i for i, n in by_id.items()}

    graph: dict[str, dict] = {
        note_id: {
            "url": f"/{note_id}/",
            "title": note.title,
            "type": note.meta.get("note_type") or "note",
            "outbound": [],
            "inbound": [],
        }
        for note_id, note in by_id.items()
    }

    for ref in links:
        if ref.status != "published" or not ref.target_id:
            continue
        source_id = slug_to_id.get(ref.source)
        if not source_id or ref.target_id not in graph:
            continue
        if ref.target_id == source_id:
            continue  # a note linking to itself adds nothing
        if ref.target_id not in graph[source_id]["outbound"]:
            graph[source_id]["outbound"].append(ref.target_id)
        if source_id not in graph[ref.target_id]["inbound"]:
            graph[ref.target_id]["inbound"].append(source_id)

    extra_titles: list[str] = []
    if content_dir and content_dir.exists():
        extra_titles = ingest_repo_pages(content_dir, graph)

    assert_no_leaks(graph, registry, extra_titles)
    return graph


def assert_no_leaks(graph: dict, registry: Registry,
                    extra_titles: list[str] | None = None) -> None:
    """Fail the export if the graph names anything unpublished.

    By construction it can't — but this is the guarantee the whole privacy
    design rests on, and a guarantee that isn't checked is a hope. Cheap to
    verify, catastrophic to get wrong.
    """
    published_titles = {n.title for n in registry.published}
    # Repo-authored pages are published by definition — they exist only in
    # content/ — but they're not in the registry, so they're allowed explicitly.
    published_titles |= set(extra_titles or [])
    published_ids = set(graph)

    for note_id, node in graph.items():
        if node["title"] not in published_titles:
            raise LeakError(
                f"graph node {note_id} has title {node['title']!r}, "
                "which belongs to no published note"
            )
        for edge in node["outbound"] + node["inbound"]:
            if edge not in published_ids:
                raise LeakError(
                    f"graph node {note_id} references {edge}, which is not a "
                    "published node"
                )


FRONTMATTER_STRIP_RE = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*\r?\n?", re.DOTALL)


def apply_presentation(
    note_id: str,
    presentation_root: Path,
    to_copy: dict[str, Path],
    taken: set[str],
) -> tuple[str | None, list[str]]:
    """Fold a repo-side presentation bundle into a note's output.

    Returns (body override or None, copied filenames).

    Two modes, distinguished by whether the directory contains an index.md:

      STYLE  style.css and friends only. The vault's body is published, wearing
             the repo's design. Nothing about rendering enters the vault.

      BODY   index.md as well. The repo's body is published instead of the
             vault's — for pages built out of markup rather than written as
             prose. The vault note keeps the draft, so the writing is still
             archived, searchable, and linkable; only the *published* form
             diverges. That divergence is the point, not a defect.

    Metadata never comes from here. Title, id, tags, dates, and the graph all
    stay owned by the vault, so there's nothing to keep in sync but prose.
    """
    if not presentation_root.exists():
        return None, []
    directory = presentation_root / note_id
    if not directory.is_dir():
        return None, []

    body_override = None
    copied: list[str] = []

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.name == "index.md":
            raw = path.read_text(encoding="utf-8", errors="replace")
            # A frontmatter block here would be ignored anyway — strip it so it
            # can't end up rendered as text.
            body_override = FRONTMATTER_STRIP_RE.sub("", raw)
            continue
        dest = asset_dest_name(path, taken) if path.name in taken else path.name
        taken.add(dest)
        to_copy[dest] = path
        copied.append(dest)

    return body_override, copied


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


def resolve_artifacts(
    body: str,
    note: Note,
    registry: Registry,
    to_copy: dict[str, Path],
    assets: list[AssetRef],
    taken: set[str],
) -> str:
    """Swap ```artifact fences for iframes, copying the referenced .html.

    The fence carries `src:` (a filename resolved like any embed) and an
    optional `height:`. A missing source is recorded and the fence dropped,
    mirroring the missing-image path. Runs before masking so the fence never
    survives to the output as literal code.
    """
    def replace(match: re.Match) -> str:
        fields = dict(ARTIFACT_FIELD_RE.findall(match.group("inner")))
        src = (fields.get("src") or "").strip().strip("\"'")
        if not src:
            return ""

        source = registry.find_asset(src)
        if source is None:
            assets.append(AssetRef(note.slug, src, None, "missing"))
            return ""

        dest = asset_dest_name(source, taken)
        to_copy[dest] = source
        assets.append(AssetRef(note.slug, src, dest, "copied"))

        height = (fields.get("height") or "").strip()
        height = height if height.isdigit() else "600"
        title = html.escape(note.title, quote=True)
        return (
            f'<iframe class="artifact-frame" src="{dest}" title="{title}"'
            f' height="{height}" loading="lazy"></iframe>'
        )

    return ARTIFACT_FENCE_RE.sub(replace, body)


def transform(note: Note, registry: Registry) -> tuple[str, list[LinkRef], list[AssetRef], dict[str, Path]]:
    """Resolve embeds and flatten wikilinks.

    Returns (body, link refs, asset refs, {dest filename: source path}).
    """
    links: list[LinkRef] = []
    assets: list[AssetRef] = []
    to_copy: dict[str, Path] = {}
    taken: set[str] = set()

    # Artifact fences resolve first, before masking would stash them as code.
    body = resolve_artifacts(note.body, note, registry, to_copy, assets, taken)
    body, stash = _mask(body)

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

        if hit is None:
            status = "dangling"
        elif hit.is_source:
            # Material Bryan didn't write. The note itself is private and
            # unpublishable, but if it records where it came from, the link
            # becomes a citation pointing at the original rather than a dead
            # phrase. Without a url there is nothing honest to link to.
            status = "source" if hit.url else "source-nourl"
        elif hit.published:
            status = "published"
        else:
            status = "unpublished"

        target_id = target_url = None
        if status == "published":
            # Canonical is /<id>/. An unstamped note has no permanent address
            # yet, so fall back to its slug — which is also an alias, so the
            # link keeps working once the note is stamped.
            raw_id = hit.meta.get("id")
            if is_valid(raw_id):
                target_id = str(raw_id).strip()
                target_url = f"/{target_id}/"
            else:
                target_url = f"/{hit.slug}/"

        links.append(
            LinkRef(note.slug, base, shown, bool(bang), status, target_id, target_url)
        )

        if status == "source":
            return f"[{shown}]({hit.url})"
        if status == "published":
            return f"[{shown}]({target_url})"
        # Unpublished and dangling stay as plain text — a link would expose
        # that the note exists, and its title (PRODUCT.md §7.4.2).
        return shown

    body = WIKILINK_RE.sub(replace, body)

    # Removing an embed that sat inside a blockquote leaves a bare "> " line.
    body = EMPTY_QUOTE_RE.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    return _unmask(body, stash), links, assets, to_copy


def resolve_urls(note: Note, slug_history: dict) -> tuple[str | None, list[str]]:
    """Return (canonical url, aliases), updating slug history in place.

    Canonical is `/<id>/` — permanent, because on a static host a URL either
    exists as a generated path or 404s. `/<id>/<slug>/` would break on rename;
    only an id-as-whole-path is truly immutable (PRODUCT.md §12.1).

    Every slug the note has ever had becomes an alias redirecting to canonical.
    """
    note_id = note.meta.get("id")
    if not is_valid(note_id):
        return None, []
    note_id = str(note_id).strip()

    record = slug_history.setdefault(note_id, {"current": note.slug, "previous": []})
    if record["current"] != note.slug:
        # Renamed. The old slug keeps redirecting — forever, deliberately.
        if record["current"] not in record["previous"]:
            record["previous"].append(record["current"])
        record["current"] = note.slug
    record["previous"] = [s for s in record["previous"] if s != note.slug]

    aliases = [f"/{s}/" for s in [record["current"], *record["previous"]]]
    return f"/{note_id}/", aliases


def build_frontmatter(note: Note, config: dict, slug_history: dict) -> dict:
    defaults = config.get("defaults", {})
    meta = note.meta

    out = {
        "title": note.title,
        "slug": note.slug,
        "type": meta.get("note_type") or defaults.get("type", "note"),
        "temporality": meta.get("temporality"),
        "draft": False,
    }

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if tags:
        out["tags"] = [str(t) for t in tags]

    # Allowlisted extras only. Everything else in the vault's frontmatter —
    # ratings, ISBNs, cast lists, page counts — stays private by omission.
    #
    # Wikilink brackets are stripped: some properties are stored as
    # "[[cover.jpeg]]" because Obsidian's Bases cards view requires that form,
    # but the site wants a plain value. The pipeline only resolves wikilinks in
    # the body, so anything left bracketed here would publish as literal
    # "[[...]]" text.
    for key in config.get("extra_fields", []):
        value = meta.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, str):
            value = re.sub(r"^\[\[(.*?)(\|.*?)?\]\]$", r"\1", value.strip())
        out[key] = value

    # An abstract, portable statement of the piece's spatial needs — NOT a
    # Hugo template name. Any generator can interpret `wide` as it likes; this
    # one widens the measure. See PRODUCT.md §5.1 for why that distinction is
    # what keeps the vault portable.
    # `wide` only. `custom` was dropped: the pipeline decides art direction by
    # finding presentation/<id>/, so a field claiming it determined nothing and
    # could disagree with reality.
    presentation = str(meta.get("presentation") or "").strip().lower()
    if presentation == "wide":
        out["presentation"] = presentation

    url, aliases = resolve_urls(note, slug_history)
    if url:
        out["id"] = str(meta["id"]).strip()
        out["url"] = url
        out["aliases"] = aliases

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
         previous_manifest: list[str] | None = None,
         slug_history: dict | None = None) -> EmitResult:
    result = EmitResult()
    content_dir = repo_root / config["content_dir"]
    slug_history = slug_history if slug_history is not None else {}
    # A relref target is a content directory name, which is the note's slug.
    by_slug = {n.slug: n for n in registry.published}

    for note in registry.published:
        if not note.slug:
            result.skipped.append((note.rel, "title produced an empty slug"))
            continue
        if not is_valid(note.meta.get("id")):
            result.unstamped.append(note.rel)

        body, links, assets, to_copy = transform(note, registry)
        result.links.extend(links)
        result.assets.extend(assets)

        front = build_frontmatter(note, config, slug_history)

        # The `cover` FIELD drives the copy, not a body embed. Notes no longer
        # carry an embed — the template places the cover — so relying on the
        # body would mean covers silently never reach the site.
        #
        # Assets are slugified on the way into the bundle, so the field is also
        # repointed at the copied filename; the two would otherwise disagree.
        cover = str(front.get("cover") or "").strip().strip("[]")
        if cover:
            source = registry.find_asset(cover)
            if source is None:
                result.assets.append(AssetRef(note.slug, cover, None, "missing"))
                front.pop("cover", None)
            else:
                already = next((d for d, s in to_copy.items() if s == source), None)
                if already:
                    front["cover"] = already
                else:
                    dest_name = asset_dest_name(source, set(to_copy))
                    to_copy[dest_name] = source
                    front["cover"] = dest_name
                    result.assets.append(
                        AssetRef(note.slug, cover, dest_name, "copied")
                    )
                # If a body embed of the same image survives, drop it so the
                # page doesn't show the cover twice.
                body = re.sub(
                    r"^!\[[^\]]*\]\(" + re.escape(front["cover"]) + r"\)[ \t]*$\n?",
                    "", body, count=1, flags=re.MULTILINE,
                )
        # ---- presentation override --------------------------------------
        # A repo-side bundle keyed by this note's permanent id supplies design,
        # and optionally a published body. The vault note is untouched and
        # remains the archive of the writing (PRODUCT.md §9.3).
        note_id = str(front.get("id") or "").strip()
        if note_id:
            override, copied = apply_presentation(
                note_id,
                repo_root / config.get("presentation_dir", "presentation"),
                to_copy,
                set(to_copy),
            )
            if override is not None or copied:
                # ONLY a body override implies the story layout. A stylesheet
                # alone means "normal page, different design" — forcing story
                # there would strip the site chrome the page still wants, and
                # collapse the two modes into one.
                #
                # This is how a "wide" page is expressed: a presentation dir
                # containing nothing but `main { max-width: 60rem }`. Base
                # styles sit in @layer base, so unlayered page CSS wins with no
                # specificity fight and no enum of blessed layout names.
                if override is not None:
                    body = override
                    front["layout"] = "story"
                result.presented.append(PresentationRef(
                    note.slug, note_id,
                    "body" if override is not None else "style",
                    copied,
                ))
                for dest_name in copied:
                    result.manifest.append(
                        str((content_dir / note.slug / dest_name).relative_to(repo_root))
                    )

                # When the body is overridden, the DRAFT's wikilinks are no
                # longer what a reader can follow — the published body's links
                # are. Parse those too, so backlinks describe the site rather
                # than the draft. Both sets count: the draft's links are real
                # links in the vault's own graph.
                if override is not None:
                    for target_slug in set(RELREF_RE.findall(body)):
                        hit = by_slug.get(target_slug)
                        if hit and is_valid(hit.meta.get("id")):
                            result.links.append(LinkRef(
                                note.slug, target_slug, target_slug, False,
                                "published", str(hit.meta["id"]).strip(),
                                f"/{str(hit.meta['id']).strip()}/",
                            ))
                    for target_id in set(ID_LINK_RE.findall(body)):
                        result.links.append(LinkRef(
                            note.slug, target_id, target_id, False,
                            "published", target_id, f"/{target_id}/",
                        ))


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
            # Guard: never delete a repo-authored page. Art-directed stories
            # live in content/ but have no vault original, so they'd otherwise
            # look like output the pipeline no longer produces.
            if is_repo_authored(stale):
                result.protected.append(rel)
                continue
            result.pruned.append(rel)
            if apply and stale.exists():
                stale.unlink()

        if apply:
            for bundle_dir in sorted(content_dir.glob("*")):
                if bundle_dir.is_dir() and not any(bundle_dir.iterdir()):
                    bundle_dir.rmdir()

    return result
