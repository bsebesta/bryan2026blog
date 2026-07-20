"""Normalise book note filenames.

    .venv/bin/python -m pipeline.rename_books           # dry run
    .venv/bin/python -m pipeline.rename_books --apply   # renames + rewrites links

WRITES TO THE VAULT, and renames files — the most disruptive thing in this
pipeline. Inbound `[[wikilinks]]` are rewritten across the whole vault in the
same pass, because Obsidian only fixes links for renames done inside Obsidian.

Why not just use the `title` field
----------------------------------
Because it's worse. Enrichment pulled titles from Open Library, which stores
them in sentence case and often merges the subtitle in:

    A Secular Age (book)              → "A secular age"
    Bonds That Make Us Free           → "Bonds that Make Us Free"
    1st Nephi - Brief Theological …   → "1st Nephi A Brief Theological Introduction"

The filenames are Bryan's own and read better. So this cleans them rather than
replacing them:

  * drop "(book)", "(book by X)", "(by X)" suffixes
  * drop a trailing "(Author Name)" when it matches the note's own authors
  * convert any surviving kebab-case slug to title case
  * collapse doubled whitespace

Anything that would collide with another note is left alone and reported —
usually two genuinely different books sharing a title, where the author suffix
is doing real work.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

BOOKS_DIR = "Logbook/Books"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")
PAREN_TAIL_RE = re.compile(r"\s*\(([^)]+)\)\s*$")

SMALL_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "of", "in",
               "on", "at", "to", "from", "by", "with", "as", "is", "it"}


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def split_frontmatter(text: str) -> dict:
    match = FM_RE.match(text)
    if not match:
        return {}
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return meta if isinstance(meta, dict) else {}


def title_case(text: str) -> str:
    words = text.split()
    out = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in SMALL_WORDS:
            out.append(word.lower())
        elif any(c.isupper() for c in word):
            out.append(word)
        else:
            out.append(word.capitalize())
    return " ".join(out)


def clean_stem(stem: str, authors: list[str]) -> str:
    new = re.sub(r"\s*\((?:book|novel|audiobook)(?:\s+by[^)]*)?\)\s*$", "", stem, flags=re.I)
    new = re.sub(r"\s*\(by [^)]*\)\s*$", "", new, flags=re.I)

    # A trailing parenthetical is dropped only when it names one of the note's
    # own authors — otherwise it may be a genuine disambiguator or a series.
    match = PAREN_TAIL_RE.search(new)
    if match and authors:
        inner = match.group(1).lower()
        surnames = [a.split()[-1].lower() for a in authors if a and a.split()]
        if any(s in inner for s in surnames):
            new = new[: match.start()].strip()

    if KEBAB_RE.match(new):
        new = title_case(new.replace("-", " "))

    return re.sub(r"\s+", " ", new).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise book note filenames.")
    parser.add_argument("--apply", action="store_true", help="Rename and rewrite links.")
    args = parser.parse_args()

    vault = Path(load_config()["vault_root"])
    books = vault / BOOKS_DIR
    if not books.exists():
        print(f"ERROR: {books} not found", file=sys.stderr)
        return 2

    existing = {p.stem for p in books.glob("*.md")}
    proposals: list[tuple[Path, str]] = []

    for path in sorted(books.glob("*.md")):
        meta = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        authors = meta.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        new = clean_stem(path.stem, [str(a) for a in authors])
        if new and new != path.stem:
            proposals.append((path, new))

    counts = Counter(new for _, new in proposals)
    taken = existing - {p.stem for p, _ in proposals}

    renames, blocked = [], []
    for path, new in proposals:
        if counts[new] > 1 or new in taken:
            blocked.append((path, new))
        else:
            renames.append((path, new))

    print(f"\n{'─' * 72}")
    print("RENAME BOOK NOTES")
    print(f"  notes            {len(existing):>5}")
    print(f"  to rename        {len(renames):>5}")
    print(f"  blocked          {len(blocked):>5}   (would collide)")

    if renames:
        print(f"\n{'─' * 72}")
        print("RENAMES")
        for path, new in renames:
            print(f"  {path.stem[:46]:<46} → {new}")

    if blocked:
        print(f"\n{'─' * 72}")
        print("BLOCKED — target name already taken. Left as-is.")
        for path, new in blocked:
            print(f"  {path.stem[:46]:<46} ✗ {new}")

    # Inbound links, so the report shows the true blast radius.
    rename_map = {p.stem: new for p, new in renames}
    link_re = re.compile(r"\[\[([^\]|#]+)((?:[|#][^\]]*)?)\]\]")
    touched: list[tuple[Path, str, int]] = []

    for path in vault.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = 0

        def swap(match: re.Match) -> str:
            nonlocal hits
            target = match.group(1).strip()
            if target in rename_map:
                hits += 1
                return f"[[{rename_map[target]}{match.group(2)}]]"
            return match.group(0)

        updated = link_re.sub(swap, text)
        if hits:
            touched.append((path, updated, hits))

    total_links = sum(h for _, _, h in touched)
    print(f"\n{'─' * 72}")
    print(f"INBOUND LINKS TO REWRITE — {total_links} in {len(touched)} file(s)")
    for path, _, hits in touched[:12]:
        print(f"  {hits:>3}  {path.relative_to(vault)}")
    if len(touched) > 12:
        print(f"       … and {len(touched) - 12} more files")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    # Links first: rewriting before renaming means a crash mid-run leaves
    # links pointing at files that still exist, rather than at nothing.
    for path, updated, _ in touched:
        tmp = path.with_suffix(path.suffix + ".rename-tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, path)

    for path, new in renames:
        os.replace(path, path.parent / f"{new}.md")

    print(f"RENAMED {len(renames)} note(s); rewrote {total_links} link(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
