"""Audit book notes against the canonical schema. READ-ONLY.

    .venv/bin/python -m pipeline.audit_books
    .venv/bin/python -m pipeline.audit_books --list missing:cover

Writes nothing. Reports four classes of problem:

  MISSING   a field the template defines is absent or empty
  UNKNOWN   a field present in notes but not in bookschema.py
  TYPE      a field holding the wrong shape (authors as a string, publish as
            a string, cover without wikilink brackets)
  ORDER     frontmatter keys out of canonical sequence

Required vs optional matters: `subtitle`, `coverGoogle`, `highlights`, and
`description` are genuinely absent for many books and aren't worth flagging.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from .bookschema import BOOK_KEY_ORDER

BOOKS_DIR = "Logbook/Books"
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)

REQUIRED = ["publish", "title", "authors", "cover", "date", "tags"]
EXPECTED = ["publishers", "published", "publishedYear", "isbn", "pageCount",
            "shelves"]
# `rating` is a slot for Bryan to fill, not data anything can supply — flagging
# 400 unrated books as "missing" would drown the findings that matter.
# `contributors` is empty for most books and only meaningful for translations
# and edited volumes, so its absence is not a finding.
OPTIONAL = ["subtitle", "coverGoogle", "highlights", "description", "rating",
            "contributors"]

LIST_FIELDS = ("authors", "contributors", "publishers", "shelves", "tags")


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit book notes. Read-only.")
    parser.add_argument("--list", metavar="CODE",
                        help="Print every note for one finding, "
                             "e.g. missing:cover, type:authors, unknown:skills")
    args = parser.parse_args()

    books = Path(load_config()["vault_root"]) / BOOKS_DIR
    if not books.exists():
        print(f"ERROR: {books} not found", file=sys.stderr)
        return 2

    notes = []
    unparseable = []
    for path in sorted(books.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = FM_RE.match(text)
        if not match:
            unparseable.append((path, "no frontmatter"))
            continue
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            unparseable.append((path, str(exc).split("\n")[0]))
            continue
        if not isinstance(meta, dict):
            unparseable.append((path, "frontmatter is not a mapping"))
            continue
        notes.append((path, meta, match.group(2)))

    findings: dict[str, list[Path]] = defaultdict(list)
    unknown_keys: Counter = Counter()

    for path, meta, body in notes:
        for field in REQUIRED + EXPECTED:
            if meta.get(field) in (None, "", []):
                findings[f"missing:{field}"].append(path)

        for key in meta:
            if key not in BOOK_KEY_ORDER:
                unknown_keys[key] += 1
                findings[f"unknown:{key}"].append(path)

        for field in LIST_FIELDS:
            value = meta.get(field)
            if value not in (None, "", []) and not isinstance(value, list):
                findings[f"type:{field}"].append(path)

        if meta.get("publish") is not None and not isinstance(meta["publish"], bool):
            findings["type:publish"].append(path)

        cover = meta.get("cover")
        if cover and not str(cover).strip().startswith("[["):
            findings["type:cover"].append(path)

        tags = meta.get("tags") or []
        if isinstance(tags, list) and "book" not in [str(t) for t in tags]:
            findings["missing:tag-book"].append(path)

        present = [k for k in meta if k in BOOK_KEY_ORDER]
        canonical = [k for k in BOOK_KEY_ORDER if k in meta]
        if present != canonical:
            findings["order"].append(path)

        if not re.search(r"^##\s*Review", body, re.MULTILINE):
            findings["missing:review-heading"].append(path)

    print(f"\n{'─' * 72}")
    print("BOOK NOTE AUDIT")
    print(f"  notes parsed         {len(notes):>5}")
    print(f"  unparseable          {len(unparseable):>5}")

    if unparseable:
        print(f"\n{'─' * 72}")
        print("UNPARSEABLE")
        for path, why in unparseable:
            print(f"  {path.name}\n      {why}")

    def section(title: str, prefix: str) -> None:
        rows = sorted(((k, v) for k, v in findings.items() if k.startswith(prefix)),
                      key=lambda kv: -len(kv[1]))
        if not rows:
            return
        print(f"\n{'─' * 72}")
        print(title)
        for code, paths in rows:
            print(f"  {len(paths):>5}  {code}")

    section("MISSING FIELDS", "missing:")
    section("WRONG TYPE", "type:")
    section("UNKNOWN FIELDS — not in bookschema.py", "unknown:")

    if findings.get("order"):
        print(f"\n{'─' * 72}")
        print(f"OUT OF ORDER — {len(findings['order'])} note(s)")

    if args.list:
        paths = findings.get(args.list)
        print(f"\n{'─' * 72}")
        if not paths:
            print(f"No notes for {args.list!r}.")
        else:
            print(f"{args.list} — {len(paths)} note(s)")
            for path in paths:
                print(f"  {path.stem}")

    clean = len(notes) - len({p for v in findings.values() for p in v})
    print(f"\n{'─' * 72}")
    print(f"{clean} of {len(notes)} notes are fully clean.")
    print("Re-run with --list CODE to see the notes behind any line above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
