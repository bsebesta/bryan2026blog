"""Strip redundant scaffolding from book note bodies.

    .venv/bin/python -m pipeline.clean_bodies           # dry run
    .venv/bin/python -m pipeline.clean_bodies --apply   # writes to the vault

WRITES TO THE VAULT. Removes two things the migration added that have since
become redundant:

  COVER EMBED    The `cover` frontmatter field now drives everything — the
                 Bases cards view, and the site (emit.py copies the image from
                 that field and the Hugo template places it). A body embed just
                 shows the same picture twice.

  EMPTY REVIEW   "## Review" with nothing under it, in 406 of 407 notes.

A "## Review" heading with actual text under it is LEFT ALONE. Removing it
would silently fold a written review into the surrounding notes with no marker.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

BOOKS_DIR = "Logbook/Books"

FM_RE = re.compile(r"\A(---\r?\n.*?\r?\n---[ \t]*\r?\n?)(.*)\Z", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def strip_cover_embed(body: str, cover: str) -> tuple[str, bool]:
    """Remove an embed of the note's own cover image."""
    if not cover:
        return body, False
    pattern = re.compile(
        r"^!\[\[" + re.escape(cover) + r"(\|[^\]]*)?\]\][ \t]*$\n?",
        re.MULTILINE,
    )
    new, count = pattern.subn("", body)
    return new, bool(count)


def strip_empty_review(body: str) -> tuple[str, bool, bool]:
    """Remove a '## Review' heading that has no content under it.

    Returns (body, removed, kept_because_written).
    """
    match = re.search(r"^##\s*Review[ \t]*$", body, re.MULTILINE | re.IGNORECASE)
    if not match:
        return body, False, False

    after = body[match.end():]
    next_heading = HEADING_RE.search(after)
    section = after[: next_heading.start()] if next_heading else after

    if section.strip():
        return body, False, True

    new = body[: match.start()] + after[len(section):]
    return new, True, False


def tidy(body: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean book note bodies.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    args = parser.parse_args()

    books = Path(load_config()["vault_root"]) / BOOKS_DIR
    if not books.exists():
        print(f"ERROR: {books} not found", file=sys.stderr)
        return 2

    planned, kept_reviews = [], []
    covers_removed = reviews_removed = 0

    for path in sorted(books.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = FM_RE.match(text)
        if not match:
            continue
        front, body = match.group(1), match.group(2)

        try:
            meta = yaml.safe_load(front.strip().strip("-\n")) or {}
        except yaml.YAMLError:
            meta = {}
        cover = str(meta.get("cover") or "").strip().strip("[]")

        new_body, did_cover = strip_cover_embed(body, cover)
        new_body, did_review, kept = strip_empty_review(new_body)
        new_body = tidy(new_body)

        if kept:
            kept_reviews.append(path)
        if did_cover:
            covers_removed += 1
        if did_review:
            reviews_removed += 1
        if new_body != body:
            planned.append((path, front + "\n" + new_body))

    print(f"\n{'─' * 72}")
    print("CLEAN BOOK BODIES")
    print(f"  notes to change      {len(planned):>5}")
    print(f"  cover embeds removed {covers_removed:>5}")
    print(f"  empty '## Review'    {reviews_removed:>5}")
    print(f"  reviews left alone   {len(kept_reviews):>5}   (have text under them)")

    if kept_reviews:
        print(f"\n{'─' * 72}")
        print("KEPT — these have a written review")
        for path in kept_reviews:
            print(f"  {path.stem}")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    for path, rendered in planned:
        tmp = path.with_suffix(".md.clean-tmp")
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, path)

    print(f"CLEANED {len(planned)} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
