"""Give hotkey-created notes their frontmatter.

    .venv/bin/python -m pipeline.seed           # dry run
    .venv/bin/python -m pipeline.seed --apply   # writes to the vault

WRITES TO THE VAULT. Runs as the first step of `make prep`.

A note made with Obsidian's new-note hotkey has no frontmatter at all. That's
already safe — the publish gate fails closed on absence — but it means the
Properties panel is empty, so turning the note into something publishable
requires typing the field by hand, which is exactly the friction that stops a
note becoming a page.

So: add the gate, set to false, and nothing else. Type and temporality derive
from the folder; `id` is stamped at publish time; `tags` and `presentation` are
added only when wanted. One line, and the note is ready to be published by
flipping a toggle.

ONLY adds. Never edits or reorders an existing frontmatter block.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

FM_RE = re.compile(r"\A---\r?\n", re.MULTILINE)

# Where a bare note is expected. Book and film notes come from templates and
# already carry frontmatter; journal entries are private by default and don't
# need seeding to stay that way.
SEED_DIRS = ["Notebook"]


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed bare notes with frontmatter.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    args = parser.parse_args()

    vault = Path(load_config()["vault_root"])
    planned = []

    for folder in SEED_DIRS:
        directory = vault / folder
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if FM_RE.match(text):
                continue
            planned.append((path, "---\npublish: false\n---\n\n" + text.lstrip("\n")))

    print(f"\n{'─' * 72}")
    print("SEED BARE NOTES")
    print(f"  notes without frontmatter  {len(planned):>4}")

    if planned:
        print(f"\n{'─' * 72}")
        for path, _ in planned:
            print(f"  + publish: false   {path.relative_to(vault)}")

    print(f"\n{'─' * 72}")
    if not planned:
        print("Nothing to seed.")
        return 0
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    for path, rendered in planned:
        tmp = path.with_suffix(".md.seed-tmp")
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, path)

    print(f"SEEDED {len(planned)} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
