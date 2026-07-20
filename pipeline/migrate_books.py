"""One-time migration: bring past book notes into Bryan's Notes.

    .venv/bin/python -m pipeline.migrate_books           # dry run
    .venv/bin/python -m pipeline.migrate_books --apply   # copies files
    .venv/bin/python -m pipeline.migrate_books --apply --move   # and deletes source

WRITES TO THE VAULT. Copies by default — the originals stay in Past Writing
until you've checked the result, because 1,055 files is too many to undo by
hand. Add --move once you're satisfied.

The split
---------
Two populations live in Past Writing/Books:

  * READWISE EXPORTS (~540) — verbatim passages from copyrighted books, often
    dozens per file. Under the vault's own rule (~ Attachments is anything
    Bryan didn't write) these are source material. They go to
    ~ Attachments/Readwise/, where publishing them is structurally impossible.

  * STRUCTURED RECORDS (~515) — Bryan's own book log, with metadata from the
    old Google Books script. These go to Logbook/Books/ and become publishable
    once he writes a review.

Where both exist for the same book, the log entry links to its highlights.

Detection is by content (`## Highlights`), not filename, because ~14 Readwise
re-exports are named `… (Readwise)-2.md` and similar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import yaml

from .bookschema import BOOK_KEY_ORDER, order_frontmatter, tidy_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE_BOOKS = "Bryan's Past Writing/Books"
SOURCE_COVERS = "Bryan's Past Writing/_Orphans/Notes (2021-2024)/~ Sourcebook/Logbook/Book Covers"

DEST_BOOKS = "Logbook/Books"
DEST_READWISE = "~ Attachments/Readwise"
DEST_COVERS = "~ Attachments/Images/Covers"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
HIGHLIGHTS_RE = re.compile(r"^## Highlights", re.MULTILINE)

# Frontmatter order lives in bookschema.py so every script that writes a book
# note agrees. See that module for the vocabulary rationale.
KEY_ORDER = BOOK_KEY_ORDER


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


def base_title(name: str) -> str:
    """'A Brief History of Thought (by Luc Ferry) (Readwise)-2' → 'A Brief History of Thought'."""
    name = re.sub(r"\s*\(Readwise\)(-\d+)?$", "", name)
    name = re.sub(r"\s*\(by [^)]*\)\s*$", "", name)
    return name.strip()


def normalise_shelves(value) -> list[str]:
    """Lowercase and de-duplicate. The vault has 'non-fiction', 'Non-fiction',
    and stray indented entries that parsed as separate values."""
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    out, seen = [], set()
    for item in value:
        s = str(item).strip().lower().replace(" ", "-")
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        # "Jordan B. Peterson" stays one author; "A, B" splits.
        return [p.strip() for p in value.split(",") if p.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def build_note(meta: dict, body: str, highlights_link: str | None) -> str:
    out: dict = {}

    out["publish"] = bool(meta.get("publish") is True or meta.get("publish") == "true")
    for key in ("title", "subtitle"):
        if meta.get(key):
            out[key] = meta[key]

    for key in ("authors", "publishers"):
        vals = as_list(meta.get(key))
        if vals:
            out[key] = vals

    for key in ("published", "publishedYear", "isbn", "pageCount",
                "coverGoogle", "date", "dateYear"):
        if meta.get(key) not in (None, ""):
            out[key] = meta[key]

    # Bases' Cards view only renders a cover when the property is a wikilink,
    # a URL, or a hex colour — a bare filename shows nothing. So `cover` is
    # stored as "[[file.jpeg]]".
    #
    # emit.py strips the brackets on the way to the site, and the body embed
    # below is what actually gets the image copied into the page bundle.
    cover = meta.get("cover")
    if cover:
        cover = str(cover).strip()
        if not cover.startswith("[["):
            cover = f"[[{cover}]]"
        out["cover"] = cover

    out["rating"] = meta.get("rating") or None

    # Wikilink in frontmatter. PyYAML quotes it (a bare "[[" would parse as a
    # nested flow sequence), and Obsidian renders quoted wikilinks as real
    # links in the Properties panel.
    #
    # NOTE: the export pipeline resolves wikilinks in the BODY only. This one
    # is never rewritten — which is fine, because `highlights` isn't in
    # extra_fields and so never reaches the site. Don't add it there without
    # teaching emit.py to resolve frontmatter links first.
    if highlights_link:
        out["highlights"] = f"[[{highlights_link}]]"

    shelves = normalise_shelves(meta.get("shelves"))
    if shelves:
        out["shelves"] = shelves

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t) for t in tags]
    if "book" not in tags:
        tags.insert(0, "book")
    out["tags"] = tags

    if meta.get("description"):
        out["description"] = meta["description"]

    ordered = order_frontmatter(out, KEY_ORDER)

    front = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True,
                           default_flow_style=False, width=10000)
    front = tidy_yaml(front)

    body = body.strip()

    parts = ["---\n" + front + "---\n"]
    if meta.get("cover"):
        bare = str(meta["cover"]).strip().strip("[]")
        parts.append(f"\n![[{bare}]]\n")
    if body:
        parts.append("\n" + body + "\n")
    if "## Review" not in body:
        parts.append("\n## Review\n\n")

    # No body embed of the highlights file — some run to hundreds of lines,
    # and transcluding that would bury the review. The frontmatter link is
    # enough, and Obsidian surfaces it in the Properties panel.

    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate past book notes into the vault.")
    parser.add_argument("--apply", action="store_true", help="Write files.")
    parser.add_argument("--move", action="store_true",
                        help="Delete source files after a successful copy.")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    past = vault.parent / SOURCE_BOOKS
    covers_src = vault.parent / SOURCE_COVERS

    if not past.exists():
        print(f"ERROR: source not found at {past}", file=sys.stderr)
        return 2

    notes = sorted(past.glob("*.md"))
    readwise, structured = [], []
    for path in notes:
        text = path.read_text(encoding="utf-8", errors="replace")
        (readwise if HIGHLIGHTS_RE.search(text) else structured).append((path, text))

    # Rename highlights files to match their book, service-agnostically:
    #   "A Brief History of Thought (by Luc Ferry) (Readwise)" →
    #   "A Brief History of Thought (Highlights)"
    #
    # "Readwise" is where the highlights came from, not what they are. If the
    # export tool changes, the filenames shouldn't.
    #
    # Readwise re-exports arrive as -2/-3/-4 suffixes and would collide on the
    # same title, so those get numbered instead.
    rw_names: dict[str, str] = {}
    taken: set[str] = set()
    for path, _ in readwise:
        base = base_title(path.stem)
        candidate = f"{base} (Highlights)"
        counter = 2
        while candidate.lower() in taken:
            candidate = f"{base} (Highlights {counter})"
            counter += 1
        taken.add(candidate.lower())
        rw_names[path.stem] = candidate

    # Pair structured records with their highlights file, by base title.
    # Stores the NEW name, so the frontmatter link points at the renamed file.
    rw_by_title: dict[str, str] = {}
    for path, _ in readwise:
        rw_by_title.setdefault(base_title(path.stem).lower(), rw_names[path.stem])

    planned_books, planned_covers, missing_covers = [], [], []
    pairs = 0
    shelf_tally: Counter = Counter()

    for path, text in structured:
        meta, body = split_frontmatter(text)
        title_key = base_title(path.stem).lower()
        link = rw_by_title.get(title_key)
        if link:
            pairs += 1

        shelf_tally.update(normalise_shelves(meta.get("shelves")))

        cover = meta.get("cover")
        if cover:
            src = covers_src / str(cover)
            if src.exists():
                planned_covers.append(src)
            else:
                missing_covers.append((path.stem, str(cover)))

        planned_books.append((path, build_note(meta, body, link)))

    # ---- report --------------------------------------------------------
    print(f"\n{'─' * 72}")
    print("BOOK MIGRATION")
    print(f"  notes in Past Writing/Books   {len(notes):>5}")
    print(f"    Readwise highlights         {len(readwise):>5}  → {DEST_READWISE}/")
    print(f"    structured records          {len(structured):>5}  → {DEST_BOOKS}/")
    print(f"  paired (log links highlights) {pairs:>5}")
    print(f"  cover images found            {len(set(planned_covers)):>5}  → {DEST_COVERS}/")
    print(f"  covers referenced but missing {len(missing_covers):>5}")

    renamed_examples = [
        (old, new) for old, new in sorted(rw_names.items()) if old != new
    ]
    if renamed_examples:
        print(f"\n{'─' * 72}")
        print("HIGHLIGHTS FILES RENAMED — dropping the service name")
        for old, new in renamed_examples[:6]:
            print(f"  {old}\n    → {new}")
        numbered = [n for _, n in renamed_examples if re.search(r"\(Highlights \d+\)$", n)]
        if numbered:
            print(f"\n  {len(numbered)} re-export duplicates numbered to avoid collisions, e.g.")
            for n in numbered[:3]:
                print(f"    {n}")
        print(f"\n  … {len(renamed_examples)} renamed in total")

    if shelf_tally:
        print(f"\n{'─' * 72}")
        print("SHELVES after normalisation (lowercased, de-duplicated)")
        for shelf, count in shelf_tally.most_common(12):
            print(f"  {count:>4}  {shelf}")

    if missing_covers:
        print(f"\n{'─' * 72}")
        print("MISSING COVER FILES — note keeps the reference; re-fetch later")
        for stem, cover in missing_covers[:10]:
            print(f"  {stem}\n      {cover}")
        if len(missing_covers) > 10:
            print(f"  … and {len(missing_covers) - 10} more")

    print(f"\n{'─' * 72}")
    print("EVERY IMPORTED NOTE IS publish: false.")
    print("Metadata migrates; reviews do not exist yet and must be written.")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — nothing written.")
        print("Re-run with --apply (add --move to delete the originals).")
        return 0

    books_dir = vault / DEST_BOOKS
    rw_dir = vault / DEST_READWISE
    cov_dir = vault / DEST_COVERS
    for d in (books_dir, rw_dir, cov_dir):
        d.mkdir(parents=True, exist_ok=True)

    manifest = []

    for path, rendered in planned_books:
        dest = books_dir / path.name
        dest.write_text(rendered, encoding="utf-8")
        manifest.append({"from": str(path), "to": str(dest)})

    for path, text in readwise:
        dest = rw_dir / f"{rw_names[path.stem]}.md"
        shutil.copy2(path, dest)
        manifest.append({"from": str(path), "to": str(dest)})

    for src in set(planned_covers):
        dest = cov_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)

    if args.move:
        for path, _ in structured + readwise:
            path.unlink()

    manifest_path = REPO_ROOT / "pipeline/state/book-migration.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"IMPORTED {len(planned_books)} book notes and {len(readwise)} highlight files.")
    print(f"Copied {len(set(planned_covers))} covers.")
    print(f"Manifest: {manifest_path.relative_to(REPO_ROOT)}")
    if not args.move:
        print("\nOriginals left in Past Writing. Re-run with --move once satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
