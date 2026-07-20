"""Pass 1 — scan the entire vault and build the note registry.

READ-ONLY. This module must never write to the vault.

The full vault is indexed, not just published notes. That is a requirement,
not an optimization: you cannot correctly decide how to render a link to a
private note unless you know the note exists (PRODUCT.md §7.2).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)


# --------------------------------------------------------------------------
# The publish gate
# --------------------------------------------------------------------------

# Obsidian's Properties UI writes booleans as *strings*. As of 2026-07-20 the
# vault contains 132 notes with the string "false" and 1 with "true".
# `if meta.get("publish"):` publishes all 133, because "false" is a non-empty
# string. This function is the reason the pipeline exists in this shape.
#
# Strict allowlist. Silently declining to publish is safe; silently publishing
# is not. Anything unrecognized fails closed and is reported.
_TRUE = {"true"}
_FALSE = {"false", ""}


def is_published(value: Any) -> bool:
    """Return True only for unambiguously-true values. Fail closed."""
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in _TRUE:
        return True
    return False


def is_ambiguous(value: Any) -> bool:
    """True if `publish` is present but neither clearly true nor clearly false.

    Such values do not publish, but they are surfaced so typos ('ture', 'yes',
    'True ') are visible rather than silently swallowed.
    """
    if value is None or value is True or value is False:
        return False
    if isinstance(value, str) and value.strip().lower() in (_TRUE | _FALSE):
        return False
    return True


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a note into (frontmatter dict, body). Tolerates missing frontmatter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw, body = match.group(1), match.group(2)
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError:
        # Malformed frontmatter fails closed: no metadata means no publish flag.
        return {"__yaml_error__": True}, body
    return (meta if isinstance(meta, dict) else {}), body


def slugify(text: str) -> str:
    """Filename- and URL-safe slug.

    Apostrophes are dropped rather than converted to hyphens, so "don't"
    becomes "dont" and not "don-t".
    """
    s = unicodedata.normalize("NFKD", text)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"['‘’]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------


@dataclass
class Note:
    path: Path
    rel: str
    title: str
    slug: str
    published: bool
    meta: dict
    body: str
    aliases: list = field(default_factory=list)
    publish_raw: Any = None
    ambiguous_publish: bool = False
    yaml_error: bool = False


# Embed targets with these suffixes are assets, not notes.
ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif",
    ".pdf", ".mp4", ".mov", ".webm", ".mp3", ".m4a", ".wav",
    ".html", ".canvas",
}


@dataclass
class Registry:
    notes: list[Note] = field(default_factory=list)
    by_title: dict[str, list[Note]] = field(default_factory=dict)
    unreadable: list[tuple[str, str]] = field(default_factory=list)
    # filename (lowercased) → path. Obsidian resolves embeds by bare filename
    # regardless of folder, so the index is keyed the same way.
    assets: dict[str, Path] = field(default_factory=dict)
    asset_collisions: dict[str, list[Path]] = field(default_factory=dict)

    def find_asset(self, name: str) -> Path | None:
        return self.assets.get(name.strip().lower())

    @property
    def published(self) -> list[Note]:
        return [n for n in self.notes if n.published]

    def lookup(self, name: str) -> Note | None:
        """Resolve a wikilink target by title or alias. None if not in vault."""
        hits = self.by_title.get(name.strip().lower())
        return hits[0] if hits else None

    def collisions(self) -> dict[str, list[Note]]:
        return {k: v for k, v in self.by_title.items() if len(v) > 1}


def scan_assets(reg: Registry, vault_root: Path, exclude_dirs: list[str]) -> None:
    """Index every non-markdown file in the vault by bare filename.

    Uses a different exclusion list from note scanning: "~ Attachments" is
    excluded for notes but is exactly where assets live.
    """
    excluded = set(exclude_dirs)
    for path in sorted(vault_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ASSET_SUFFIXES:
            continue
        if any(part in excluded for part in path.relative_to(vault_root).parts):
            continue
        key = path.name.lower()
        if key in reg.assets:
            reg.asset_collisions.setdefault(key, [reg.assets[key]]).append(path)
            continue  # first match wins; collision is reported
        reg.assets[key] = path


def scan(vault_root: Path, exclude_dirs: list[str], temporality_by_folder: dict,
         default_temporality: str) -> Registry:
    """Walk the whole vault and index every note."""
    reg = Registry()
    excluded = set(exclude_dirs)

    for path in sorted(vault_root.rglob("*.md")):
        if any(part in excluded for part in path.relative_to(vault_root).parts):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # Dropbox online-only placeholders land here. Reported, never
            # skipped silently — a silent skip in a publishing pipeline is
            # the worst available failure mode (PRODUCT.md §7.6).
            reg.unreadable.append((str(path.relative_to(vault_root)), str(exc)))
            continue

        meta, body = split_frontmatter(text)
        yaml_error = bool(meta.pop("__yaml_error__", False))

        title = str(meta.get("title") or path.stem).strip()
        publish_raw = meta.get("publish")

        top_folder = path.relative_to(vault_root).parts[0]
        meta.setdefault(
            "temporality", temporality_by_folder.get(top_folder, default_temporality)
        )

        aliases = meta.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]

        note = Note(
            path=path,
            rel=str(path.relative_to(vault_root)),
            title=title,
            slug=slugify(title),
            published=is_published(publish_raw),
            meta=meta,
            body=body,
            aliases=[str(a) for a in aliases],
            publish_raw=publish_raw,
            ambiguous_publish=is_ambiguous(publish_raw),
            yaml_error=yaml_error,
        )
        reg.notes.append(note)

        for key in [title] + note.aliases:
            reg.by_title.setdefault(key.strip().lower(), []).append(note)

    return reg
