"""Stamp permanent ids into vault frontmatter.

    .venv/bin/python -m pipeline.stamp            # dry run — shows exact diffs
    .venv/bin/python -m pipeline.stamp --apply    # writes to the vault

THIS IS THE ONE COMMAND THAT WRITES TO THE VAULT.

It is deliberately separate from `export` (PRODUCT.md §7.3). If export both
stamped and ran in CI, CI would write back into Dropbox — a sync hazard and a
way to lose an id silently.

Only published notes are stamped. An id is a promise about a URL, and private
notes have no URLs, so there is nothing to promise. That keeps this command
touching a few dozen files rather than a few thousand.

Insertion is TEXTUAL, not a YAML round-trip
-------------------------------------------
Re-serializing frontmatter with PyYAML would reformat the whole block —
reordering keys, changing `publish: "true"` to `publish: 'true'`, collapsing
list styles. That rewrites files Obsidian owns and produces noisy Dropbox
diffs. So this inserts a single `id:` line and touches nothing else.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

from .ids import generate, is_valid
from .registry import scan

REPO_ROOT = Path(__file__).resolve().parent.parent

FM_RE = re.compile(r"\A(---\r?\n)(.*?)(\r?\n---[ \t]*\r?\n?)", re.DOTALL)
ID_LINE_RE = re.compile(r"^id:", re.MULTILINE)


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def insert_id(text: str, note_id: str) -> str | None:
    """Return text with `id:` inserted, or None if it already has one."""
    match = FM_RE.match(text)
    if match:
        opening, body, closing = match.groups()
        if ID_LINE_RE.search(body):
            return None
        return opening + f"id: {note_id}\n" + body + closing + text[match.end():]
    # No frontmatter at all — create a minimal block.
    return f"---\nid: {note_id}\n---\n\n" + text.lstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stamp permanent ids into published notes. Writes to the vault."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Write to the vault. Without this flag nothing is written.")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    if not vault.exists():
        print(f"ERROR: vault not found at {vault}", file=sys.stderr)
        return 2

    registry = scan(
        vault,
        config.get("exclude_dirs", []),
        config.get("temporality_by_folder", {}),
        config.get("default_temporality", "evergreen"),
    )

    # Collect every id already in the vault, published or not, so generation
    # can avoid them.
    existing: set[str] = set()
    malformed: list[tuple[str, object]] = []
    for note in registry.notes:
        value = note.meta.get("id")
        if value is None:
            continue
        if is_valid(value):
            existing.add(str(value).strip())
        else:
            malformed.append((note.rel, value))

    needs: list = [n for n in registry.published if not is_valid(n.meta.get("id"))]
    already = len(registry.published) - len(needs)

    print(f"\n{'─' * 72}")
    print("STAMP")
    print(f"  published notes        {len(registry.published):>4}")
    print(f"    already stamped      {already:>4}")
    print(f"    need an id           {len(needs):>4}")
    print(f"  ids already in vault   {len(existing):>4}")

    if malformed:
        print(f"\n{'─' * 72}")
        print("MALFORMED ids — left alone, fix by hand")
        for rel, value in malformed:
            print(f"  {rel}\n    id: {value!r}")

    if not needs:
        print(f"\n{'─' * 72}")
        print("Nothing to stamp.")
        return 0

    print(f"\n{'─' * 72}")
    print("PLANNED CHANGES")

    planned: list[tuple] = []
    for note in needs:
        note_id = generate(existing)
        existing.add(note_id)
        try:
            original = note.path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"  SKIP {note.rel}\n    {exc}")
            continue
        updated = insert_id(original, note_id)
        if updated is None:
            continue
        planned.append((note, note_id, updated))

        print(f"\n  {note.rel}")
        print(f"    + id: {note_id}")
        print(f"    canonical URL → /{note_id}/")
        print(f"    alias         → /{note.slug}/")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print(f"DRY RUN — vault untouched. {len(planned)} note(s) would be stamped.")
        print("Re-run with --apply to write.")
        return 0

    written = 0
    for note, note_id, updated in planned:
        # Atomic replace: write a sibling temp file, then rename. A crash
        # mid-write leaves the original note intact rather than truncated.
        tmp = note.path.with_suffix(note.path.suffix + ".stamp-tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, note.path)
        written += 1

    print(f"STAMPED {written} note(s) in the vault.")
    print("Run `make apply` to regenerate the site with canonical id URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
