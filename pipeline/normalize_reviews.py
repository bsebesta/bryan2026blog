"""Restructure media note bodies into `# Shared Review` / `# Private Notes`.

    .venv/bin/python -m pipeline.normalize_reviews           # dry run
    .venv/bin/python -m pipeline.normalize_reviews --apply    # writes to the vault

WRITES TO THE VAULT. Only the `# Shared Review` section publishes (config
`publish_section`, PRODUCT.md §7.7). This one-time migration gives every media
note that clean separation:

  - an existing "## Review" (books/films) or "## Response" (music) section with
    real content is PROMOTED into `# Shared Review`;
  - everything else — reading notes, quotations, outlines, the capture template's
    comment — is tucked under `# Private Notes`;
  - a note with no real review gets an empty `# Shared Review` placeholder, so
    there's an obvious slot to write into later, and the whole body goes private.

Idempotent: a note that already has a `# Shared Review` heading is left alone.
HTML comments don't count as "real" review content. Covers Logbook/Books,
Logbook/Movies, and Logbook/Music/{Albums,Tracks,Artists} — every type: log dir.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

DIRS = [
    "Logbook/Books",
    "Logbook/Movies",
    "Logbook/Music/Albums",
    "Logbook/Music/Tracks",
    "Logbook/Music/Artists",
]

FM_RE = re.compile(r"\A(---\r?\n.*?\r?\n---[ \t]*\r?\n?)(.*)\Z", re.DOTALL)
REVIEW_RE = re.compile(r"^##[ \t]*(?:Review|Response)[ \t]*$", re.MULTILINE | re.IGNORECASE)
BOUNDARY_RE = re.compile(r"^#{1,2}[ \t]+\S", re.MULTILINE)  # next h1/h2, not deeper
ALREADY_RE = re.compile(r"^#[ \t]+Shared Review[ \t]*$", re.MULTILINE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def has_real(text: str) -> bool:
    return bool(COMMENT_RE.sub("", text or "").strip())


def extract_review(body: str) -> tuple[str, str]:
    """Return (review_section_content, everything_else)."""
    m = REVIEW_RE.search(body)
    if not m:
        return "", body
    after = body[m.end():]
    nb = BOUNDARY_RE.search(after)
    content = after[: nb.start()] if nb else after
    rest = body[: m.start()] + (after[nb.start():] if nb else "")
    return content, rest


def normalize(body: str) -> tuple[str, bool]:
    """Return (new_body, promoted). `promoted` is True when a real review moved
    into Shared Review."""
    review, rest = extract_review(body)
    promoted = has_real(review)
    if promoted:
        shared, private = review.strip(), rest.strip()
    else:
        # No real review — keep any stray content (e.g. a template comment) private.
        leftover = review.strip()
        private = (rest.strip() + ("\n\n" + leftover if leftover else "")).strip()
        shared = ""
    new = f"# Shared Review\n\n{shared}\n\n# Private Notes\n\n{private}\n"
    new = re.sub(r"\n{3,}", "\n\n", new)
    return new, promoted


def main() -> int:
    parser = argparse.ArgumentParser(description="Split media bodies into Shared Review / Private Notes.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    args = parser.parse_args()

    vault = Path(load_config()["vault_root"])
    planned: list[tuple[Path, str]] = []
    per_dir: Counter = Counter()
    promoted_paths: list[Path] = []
    already = 0

    for d in DIRS:
        folder = vault / d
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            m = FM_RE.match(text)
            if not m:
                continue
            front, body = m.group(1), m.group(2)
            if ALREADY_RE.search(body):
                already += 1
                continue
            new_body, promoted = normalize(body)
            if front + "\n" + new_body == text:
                continue
            planned.append((path, front + "\n" + new_body))
            per_dir[d] += 1
            if promoted:
                promoted_paths.append(path)

    print(f"\n{'─' * 72}")
    print("NORMALIZE MEDIA BODIES → # Shared Review / # Private Notes")
    for d in DIRS:
        if per_dir.get(d):
            print(f"  {d:<24} {per_dir[d]:>5}")
    print(f"  {'to change':<24} {len(planned):>5}")
    print(f"  {'reviews promoted':<24} {len(promoted_paths):>5}   (had real text under ## Review/## Response)")
    print(f"  {'already normalized':<24} {already:>5}   (left alone)")

    if promoted_paths:
        print(f"\n{'─' * 72}")
        print("PROMOTED — these had a written review, now under # Shared Review")
        for path in promoted_paths:
            print(f"  {path.stem}")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    for path, rendered in planned:
        tmp = path.with_suffix(".md.norm-tmp")
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, path)

    print(f"NORMALIZED {len(planned)} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
