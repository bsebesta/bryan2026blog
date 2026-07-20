"""Normalize quoted boolean `publish` values in vault frontmatter.

    .venv/bin/python -m pipeline.normalize            # dry run
    .venv/bin/python -m pipeline.normalize --apply    # writes to the vault

WRITES TO THE VAULT. Kept separate from `export` for the same reason `stamp`
is (PRODUCT.md §7.3).

Obsidian's Properties UI stores booleans as strings, so the vault accumulates
`publish: "false"` rather than `publish: false`. Both are handled correctly by
the publish gate — `is_published` accepts the string form deliberately — but
the quoted version is a standing hazard, because `"false"` is truthy in most
languages. Any future tool that reads this frontmatter without knowing the
history will publish everything.

This command removes the hazard at the source rather than defending against it
forever. It is idempotent and safe to re-run: Obsidian may reintroduce quoted
values when a property is edited through the UI.

Substitution is TEXTUAL and confined to the frontmatter block. Nothing else in
the file is touched, and body text that happens to look like a property line
is left alone.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

from .registry import scan

FM_RE = re.compile(r"\A(---\r?\n)(.*?)(\r?\n---[ \t]*\r?\n?)", re.DOTALL)
QUOTED_BOOL_RE = re.compile(
    r"^(publish:[ \t]*)([\"'])(true|false)\2[ \t]*$", re.MULTILINE | re.IGNORECASE
)


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def normalize(text: str) -> tuple[str | None, list[tuple[str, str]]]:
    """Return (updated text, [(before, after)]) or (None, []) if unchanged."""
    match = FM_RE.match(text)
    if not match:
        return None, []
    opening, body, closing = match.groups()
    changes: list[tuple[str, str]] = []

    def sub(m: re.Match) -> str:
        after = f"{m.group(1)}{m.group(3).lower()}"
        changes.append((m.group(0).strip(), after.strip()))
        return after

    new_body = QUOTED_BOOL_RE.sub(sub, body)
    if not changes:
        return None, []
    return opening + new_body + closing + text[match.end():], changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert quoted boolean `publish` values to real booleans."
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

    planned: list[tuple] = []
    tally: dict[str, int] = {}
    for note in registry.notes:
        try:
            original = note.path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated, changes = normalize(original)
        if updated is None:
            continue
        planned.append((note, updated))
        for before, after in changes:
            tally[f"{before}  →  {after}"] = tally.get(f"{before}  →  {after}", 0) + 1

    print(f"\n{'─' * 72}")
    print("NORMALIZE `publish`")
    print(f"  notes scanned          {len(registry.notes):>6,}")
    print(f"  notes to change        {len(planned):>6,}")

    if tally:
        print(f"\n{'─' * 72}")
        print("SUBSTITUTIONS")
        for line, count in sorted(tally.items()):
            print(f"  {count:>4} ×  {line}")

    if not planned:
        print(f"\n{'─' * 72}")
        print("Nothing to normalize.")
        return 0

    print(f"\n{'─' * 72}")
    if not args.apply:
        print(f"DRY RUN — vault untouched. {len(planned)} note(s) would change.")
        print("Re-run with --apply to write.")
        return 0

    written = 0
    for note, updated in planned:
        # Atomic replace, as in stamp.py: a crash mid-write leaves the
        # original note intact rather than truncated.
        tmp = note.path.with_suffix(note.path.suffix + ".norm-tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, note.path)
        written += 1

    print(f"NORMALIZED {written} note(s) in the vault.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
