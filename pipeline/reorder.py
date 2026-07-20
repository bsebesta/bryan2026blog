"""Reorder frontmatter in book and film notes to the canonical sequence.

    .venv/bin/python -m pipeline.reorder           # dry run
    .venv/bin/python -m pipeline.reorder --apply   # writes to the vault

WRITES TO THE VAULT. Changes key ORDER only — no value is added, removed, or
altered. Unknown keys keep their relative position at the end rather than being
dropped.

Separate from `normalize`, which makes careful textual edits to notes Obsidian
owns. This does a full YAML round-trip, which is only safe on notes the
pipeline generated in the first place — Logbook/Books and Logbook/Movies.

Needed because reordering happens when a script writes a note, so notes written
by an earlier version of a script keep whatever order they had.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

from .bookschema import BOOK_KEY_ORDER, MOVIE_KEY_ORDER, order_frontmatter, tidy_yaml

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)

TARGETS = [
    ("Logbook/Books", BOOK_KEY_ORDER),
    ("Logbook/Movies", MOVIE_KEY_ORDER),
]


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Reorder book/film frontmatter.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    args = parser.parse_args()

    vault = Path(load_config()["vault_root"])
    changed, scanned, skipped = [], 0, 0

    for folder, key_order in TARGETS:
        directory = vault / folder
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            scanned += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            match = FM_RE.match(text)
            if not match:
                continue
            try:
                meta = yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                skipped += 1
                continue
            if not isinstance(meta, dict) or not meta:
                continue

            ordered = order_frontmatter(meta, key_order)
            if list(ordered.keys()) == list(meta.keys()):
                continue

            front = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True,
                                   default_flow_style=False, width=10000)
            rendered = "---\n" + tidy_yaml(front) + "---\n" + match.group(2)
            changed.append((path, rendered))

    print(f"\n{'─' * 72}")
    print("REORDER FRONTMATTER")
    print(f"  notes scanned        {scanned:>5}")
    print(f"  already canonical    {scanned - len(changed) - skipped:>5}")
    print(f"  to reorder           {len(changed):>5}")
    if skipped:
        print(f"  unparseable, skipped {skipped:>5}")

    if changed:
        print(f"\n{'─' * 72}")
        print("EXAMPLES")
        for path, _ in changed[:8]:
            print(f"  {path.parent.name}/{path.name}")
        if len(changed) > 8:
            print(f"  … and {len(changed) - 8} more")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    for path, rendered in changed:
        tmp = path.with_suffix(".md.reorder-tmp")
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, path)

    print(f"REORDERED {len(changed)} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
