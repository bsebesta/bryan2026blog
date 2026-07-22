"""Rename media notes to the filename-disambiguation convention (PRODUCT.md 12.4).

    .venv/bin/python -m pipeline.rename_media           # dry run
    .venv/bin/python -m pipeline.rename_media --apply    # renames + rewrites links

WRITES TO THE VAULT, and renames files — the most disruptive thing in this
pipeline, alongside rename_books. Inbound `[[wikilinks]]` are rewritten across
the whole vault in the same pass, because Obsidian only fixes links for renames
done inside Obsidian.

Target names, by type (see PRODUCT.md 12.4):

    Book      Title - Author (YYYY book)      translator replaces author when recorded
    Film      Title - Director (YYYY film)
    Album     Title - Artist (YYYY album)
    Track     Title - Artist (YYYY track)
    Artist    Name (artist)                   no contributor, no year
    Artifact  Title (YYYY-MM artifact)        no contributor, month included

Notes, essays, pages, journal entries, and microposts are NOT touched — they
keep the clean namespace on purpose.

Where the title comes from: for BOOKS the current filename stem (Bryan's own,
cleaner than Open Library's sentence-case `title`); for everything else the
frontmatter `title` (TMDB / MusicBrainz titles are clean). Multiple creators:
one -> the name; two -> "A & B"; three+ -> "A et al." Missing data degrades
gracefully but always keeps the type word, so cross-type disambiguation holds.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")
PAREN_TAIL_RE = re.compile(r"\s*\(([^)]+)\)\s*$")
YEAR_RE = re.compile(r"\d{4}")
ILLEGAL_RE = re.compile(r'[\\/:*?"<>|#^\[\]]')
TRANSLATOR_RE = re.compile(r"^(.*?)\s*\(\s*translat(?:or|ion)\s*\)\s*$", re.I)

SMALL_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "of", "in",
               "on", "at", "to", "from", "by", "with", "as", "is", "it"}

# dir (relative to vault), type word, and how to source each part.
TYPES = [
    {"dir": "Logbook/Books",         "word": "book",     "title": "stem",  "creator": "book",  "year": "publishedYear"},
    {"dir": "Logbook/Movies",        "word": "film",     "title": "fm",    "creator": "director", "year": "releasedYear"},
    {"dir": "Logbook/Music/Albums",  "word": "album",    "title": "fm",    "creator": "artist", "year": "releasedYear"},
    {"dir": "Logbook/Music/Tracks",  "word": "track",    "title": "fm",    "creator": "artist", "year": "releasedYear"},
    {"dir": "Logbook/Music/Artists", "word": "artist",   "title": "fm",    "creator": "none",   "year": "none"},
    {"dir": "Logbook/Artifacts",     "word": "artifact", "title": "fm",    "creator": "none",   "year": "month"},
]


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


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def title_case(text: str) -> str:
    out = []
    for i, word in enumerate(text.split()):
        if i > 0 and word.lower() in SMALL_WORDS:
            out.append(word.lower())
        elif any(c.isupper() for c in word):
            out.append(word)
        else:
            out.append(word.capitalize())
    return " ".join(out)


def clean_book_stem(stem: str, authors: list[str]) -> str:
    """Same cleaning as rename_books: drop stray (book)/(by X)/(Author) tails and
    kebab slugs, so the title base is tidy before we append the suffix."""
    new = re.sub(r"\s*\((?:book|novel|audiobook)(?:\s+by[^)]*)?\)\s*$", "", stem, flags=re.I)
    new = re.sub(r"\s*\(by [^)]*\)\s*$", "", new, flags=re.I)
    match = PAREN_TAIL_RE.search(new)
    if match and authors:
        inner = match.group(1).lower()
        surnames = [a.split()[-1].lower() for a in authors if a and a.split()]
        if any(s in inner for s in surnames):
            new = new[: match.start()].strip()
    if KEBAB_RE.match(new):
        new = title_case(new.replace("-", " "))
    return re.sub(r"\s+", " ", new).strip()


def strip_wikilink(value: str) -> str:
    m = re.match(r"^\[\[([^\]|#]+).*\]\]$", value.strip())
    return (m.group(1) if m else value).strip()


def join_names(names: list[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def year_of(value) -> str:
    m = YEAR_RE.search(str(value or ""))
    return m.group(0) if m else ""


def month_of(value) -> str:
    m = re.search(r"(\d{4})-(\d{2})", str(value or ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return year_of(value)  # fall back to bare year if no month


def title_for(spec: dict, stem: str, meta: dict) -> str:
    if spec["title"] == "stem":
        return clean_book_stem(stem, as_list(meta.get("authors")))
    t = meta.get("title")
    if t:
        return re.sub(r"\s+", " ", str(t)).strip()
    return re.sub(r"\s*\(\d{4}\)\s*$", "", stem).strip()  # last resort: strip a trailing (year)


def creator_for(spec: dict, meta: dict) -> str:
    kind = spec["creator"]
    if kind == "none":
        return ""
    if kind == "book":
        translators = []
        for c in as_list(meta.get("contributors")):
            m = TRANSLATOR_RE.match(c)
            if m:
                translators.append(m.group(1).strip())
        if translators:
            return join_names(translators)
        return join_names(as_list(meta.get("authors")))
    if kind == "director":
        return join_names(as_list(meta.get("director")))
    if kind == "artist":
        return join_names([strip_wikilink(a) for a in as_list(meta.get("artist"))])
    return ""


def year_for(spec: dict, meta: dict) -> str:
    if spec["year"] == "none":
        return ""
    if spec["year"] == "month":
        return month_of(meta.get("date"))
    return year_of(meta.get(spec["year"]))


def build_stem(title: str, creator: str, year: str, word: str) -> str:
    left = f"{title} - {creator}" if creator else title
    paren = f"{year} {word}".strip()
    stem = f"{left} ({paren})"
    return re.sub(r"\s+", " ", ILLEGAL_RE.sub("", stem)).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename media notes to the 12.4 convention.")
    parser.add_argument("--apply", action="store_true", help="Rename and rewrite links.")
    args = parser.parse_args()

    vault = Path(load_config()["vault_root"])
    if not vault.exists():
        print(f"ERROR: vault {vault} not found", file=sys.stderr)
        return 2

    existing = {p.stem for p in vault.rglob("*.md")}
    proposals: list[tuple[Path, str, str]] = []  # (path, new_stem, type word)

    for spec in TYPES:
        folder = vault / spec["dir"]
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            meta = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            title = title_for(spec, path.stem, meta)
            if not title:
                continue
            new = build_stem(title, creator_for(spec, meta), year_for(spec, meta), spec["word"])
            if new and new != path.stem:
                proposals.append((path, new, spec["word"]))

    counts = Counter(new for _, new, _ in proposals)
    taken = existing - {p.stem for p, _, _ in proposals}

    renames, blocked = [], []
    for path, new, word in proposals:
        if counts[new] > 1 or new in taken:
            blocked.append((path, new))
        else:
            renames.append((path, new))

    print(f"\n{'─' * 72}")
    print("RENAME MEDIA NOTES → PRODUCT.md 12.4 convention")
    by_word = Counter(word for _, _, word in proposals)
    for word in ("book", "film", "album", "track", "artist", "artifact"):
        if by_word.get(word):
            print(f"  {word:<9} {by_word[word]:>5}")
    print(f"  {'to rename':<9} {len(renames):>5}")
    print(f"  {'blocked':<9} {len(blocked):>5}   (would collide — left as-is)")

    if renames:
        print(f"\n{'─' * 72}\nRENAMES")
        for path, new in renames:
            print(f"  {path.stem[:44]:<44} → {new}")

    if blocked:
        print(f"\n{'─' * 72}\nBLOCKED — target already taken. Left as-is.")
        for path, new in blocked:
            print(f"  {path.stem[:44]:<44} ✗ {new}")

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

    # Links first: rewriting before renaming means a crash mid-run leaves links
    # pointing at files that still exist, rather than at nothing.
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
