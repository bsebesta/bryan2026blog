"""Merge duplicate book notes.

    .venv/bin/python -m pipeline.dedupe_books           # dry run
    .venv/bin/python -m pipeline.dedupe_books --apply   # writes to the vault

WRITES TO THE VAULT. Run before enrich_books — no point fetching a cover for a
note about to be merged away.

Duplicates arrived from several import generations and take several shapes:

    Cloud Atlas                    ←→  cloud-atlas          (Title vs kebab)
    Animal Vegetable Junk          ←→  Animal, Vegetable, Junk
    Equal Partners (Kate Mangino)  ←→  Equal Partners
    A Spacious Life                ←→  A Spacious Life (2)
    Book                           ←→  Hogfather            (same ISBN)

Two notes are the same book if they share an ISBN, or if their titles match
after normalisation. Groups are then unioned, so a chain (A shares an ISBN
with B, B shares a title with C) merges into one.

SAFETY: if two notes in a group name different authors, they're reported for
review rather than merged. Two different books can share a title, and a wrong
merge silently destroys writing.

Bodies are usually *different* passages written at different times, so nothing
is discarded — distinct passages are joined with `---` dividers.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from .bookschema import order_frontmatter, tidy_yaml

BOOKS_DIR = "Logbook/Books"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
SUFFIX_RE = re.compile(r"\s*\(\d+\)$")
EMBED_RE = re.compile(r"^!\[\[[^\]]+\]\]\s*$", re.MULTILINE)
EMPTY_REVIEW_RE = re.compile(r"\n##\s*Review\s*\n+(?=\Z|\n##)", re.IGNORECASE)
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FM_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), match.group(2)


def norm_title(text: str) -> str:
    """Collapse the ways the same title has been written across imports."""
    text = text or ""
    text = SUFFIX_RE.sub("", text)
    text = re.sub(r"\((?:book|novel|audiobook)(?:\s+by[^)]*)?\)", "", text, flags=re.I)
    text = re.sub(r"\(by[^)]*\)", "", text, flags=re.I)
    # A bare parenthetical is usually the author, e.g. "Equal Partners (Kate Mangino)".
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    text = re.sub(r"^(the|a|an)\s+", "", text.strip())
    return " ".join(text.split())


def norm_isbn(value) -> str:
    return re.sub(r"[^0-9Xx]", "", str(value or "")).upper()


def norm_author(value) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    text = re.sub(r"[^a-z ]+", "", str(value).lower())
    parts = [p for p in text.split() if len(p) > 1]
    return parts[-1] if parts else ""  # surname is the stable part


def filled(meta: dict) -> int:
    return sum(1 for v in meta.values() if v not in (None, "", [], {}))


def clean_body(body: str) -> str:
    body = EMBED_RE.sub("", body)
    body = EMPTY_REVIEW_RE.sub("\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def canonical_score(stem: str, meta: dict) -> tuple:
    """Higher is better. Prefers a human-written filename over a slug, one that
    agrees with its own title field, and the richest frontmatter."""
    not_kebab = 0 if KEBAB_RE.match(stem) else 1
    agrees = 1 if norm_title(stem) == norm_title(str(meta.get("title") or "")) else 0
    no_suffix = 0 if SUFFIX_RE.search(stem) else 1
    return (not_kebab, no_suffix, agrees, filled(meta), -len(stem))


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge duplicate book notes.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    args = parser.parse_args()

    books = Path(load_config()["vault_root"]) / BOOKS_DIR
    if not books.exists():
        print(f"ERROR: {books} not found", file=sys.stderr)
        return 2

    notes = {}
    for path in sorted(books.glob("*.md")):
        meta, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        notes[path] = (meta, clean_body(body))

    # Union-find over two kinds of key, so chains collapse into one group.
    parent: dict[Path, Path] = {p: p for p in notes}

    def find(x: Path) -> Path:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: Path, b: Path) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for key_of in (
        lambda p, m: norm_isbn(m.get("isbn")) or None,
        lambda p, m: norm_title(str(m.get("title") or p.stem)) or None,
    ):
        buckets: dict[str, list[Path]] = defaultdict(list)
        for path, (meta, _) in notes.items():
            key = key_of(path, meta)
            if key:
                buckets[key].append(path)
        for members in buckets.values():
            for other in members[1:]:
                union(members[0], other)

    groups: dict[Path, list[Path]] = defaultdict(list)
    for path in notes:
        groups[find(path)].append(path)
    dupes = {k: sorted(v) for k, v in groups.items() if len(v) > 1}

    mergeable, conflicted = [], []
    for members in dupes.values():
        authors = {norm_author(notes[p][0].get("authors")) for p in members}
        authors.discard("")
        (conflicted if len(authors) > 1 else mergeable).append(members)

    print(f"\n{'─' * 72}")
    print("DEDUPE BOOK NOTES")
    print(f"  notes                {len(notes):>5}")
    print(f"  duplicate groups     {len(dupes):>5}")
    print(f"  mergeable            {len(mergeable):>5}")
    print(f"  author conflicts     {len(conflicted):>5}   (left alone)")
    print(f"  notes after merge    {len(notes) - sum(len(m) - 1 for m in mergeable):>5}")

    if conflicted:
        print(f"\n{'─' * 72}")
        print("AUTHOR CONFLICTS — same title, different authors. Not merged.")
        for members in conflicted:
            print()
            for p in members:
                a = notes[p][0].get("authors")
                print(f"  {p.stem}\n      authors: {a}")

    planned = []
    for members in mergeable:
        canonical = max(members, key=lambda p: canonical_score(p.stem, notes[p][0]))

        merged = dict(notes[canonical][0])
        for p in members:
            for key, value in notes[p][0].items():
                if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                    merged[key] = value

        bodies, seen = [], set()
        for p in members:
            body = notes[p][1]
            key = re.sub(r"\s+", " ", body).strip().lower()
            if body and key not in seen:
                seen.add(key)
                bodies.append(body)

        planned.append((canonical, members, merged, bodies))

    print(f"\n{'─' * 72}")
    print("PLANNED MERGES")
    for canonical, members, merged, bodies in sorted(planned, key=lambda t: t[0].stem.lower()):
        print(f"\n  → {canonical.stem}")
        for p in members:
            mark = "keep " if p == canonical else "merge"
            print(f"      {mark}  {p.stem}")
        if not bodies:
            note = "no prose in any copy — metadata merge only"
        elif len(bodies) == 1:
            note = "1 passage kept"
        else:
            note = f"{len(bodies)} distinct passages joined with ---"
        print(f"             {note}")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    removed = 0
    for canonical, members, merged, bodies in planned:
        front = yaml.safe_dump(order_frontmatter(merged), sort_keys=False,
                               allow_unicode=True, default_flow_style=False, width=10000)
        parts = ["---\n" + tidy_yaml(front) + "---\n"]

        cover = str(merged.get("cover") or "").strip().strip("[]")
        if cover:
            parts.append(f"\n![[{cover}]]\n")
        if bodies:
            parts.append("\n" + "\n\n---\n\n".join(bodies) + "\n")
        if not any("## Review" in b for b in bodies):
            parts.append("\n## Review\n\n")

        tmp = canonical.with_suffix(".md.dedupe-tmp")
        tmp.write_text("".join(parts), encoding="utf-8")
        os.replace(tmp, canonical)

        for p in members:
            if p != canonical and p.exists():
                p.unlink()
                removed += 1

    print(f"MERGED {len(planned)} groups; {removed} files removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
