"""Remove a frontmatter field from book and film notes.

    .venv/bin/python -m pipeline.strip_field dateYear
    .venv/bin/python -m pipeline.strip_field dateYear --apply

WRITES TO THE VAULT. Textual removal — the line is deleted and nothing else in
the note is touched. No YAML round-trip, so key order, quoting style, and list
formatting all survive exactly as they were.

Built for `dateYear`, which existed only because Dataview could not group by a
computed value. Obsidian Bases can (`groupBy: formula.read`), so the stored
field is pure duplication of `date`.

Deliberately refuses to strip a field unless every value it holds is
reproducible from another field — see SAFE_TO_STRIP. Removing data that isn't
derivable is not a normalisation, it's a deletion.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

FOLDERS = ["Logbook/Books", "Logbook/Movies"]
FM_RE = re.compile(r"\A(---\r?\n)(.*?)(\r?\n---[ \t]*\r?\n?)(.*)\Z", re.DOTALL)

# field → (source field, how the value is reproduced)
SAFE_TO_STRIP = {
    "dateYear": ("date", "date.format(\"YYYY\")"),
}


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip a frontmatter field.")
    parser.add_argument("field", help="Field name to remove.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    parser.add_argument("--force", action="store_true",
                        help="Strip a field not listed as safely derivable.")
    args = parser.parse_args()

    if args.field not in SAFE_TO_STRIP and not args.force:
        print(f"'{args.field}' is not listed as derivable in SAFE_TO_STRIP.",
              file=sys.stderr)
        print("Removing a field that can't be recomputed loses data. Pass "
              "--force if you're certain.", file=sys.stderr)
        return 2

    vault = Path(load_config()["vault_root"])
    line_re = re.compile(rf"^{re.escape(args.field)}:.*$\n?", re.MULTILINE)

    planned, orphaned = [], []
    for folder in FOLDERS:
        directory = vault / folder
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            match = FM_RE.match(text)
            if not match:
                continue
            opening, front, closing, body = match.groups()
            if not line_re.search(front):
                continue

            # Guard: if the source field is missing, the value is NOT
            # reproducible for this note and stripping would lose it.
            if args.field in SAFE_TO_STRIP:
                source = SAFE_TO_STRIP[args.field][0]
                if not re.search(rf"^{source}:\s*\S", front, re.MULTILINE):
                    orphaned.append(path)
                    continue

            planned.append((path, opening + line_re.sub("", front) + closing + body))

    print(f"\n{'─' * 72}")
    print(f"STRIP FIELD — {args.field}")
    if args.field in SAFE_TO_STRIP:
        source, how = SAFE_TO_STRIP[args.field]
        print(f"  reproducible from `{source}` via {how}")
    print(f"  notes to change   {len(planned):>5}")
    print(f"  left alone        {len(orphaned):>5}   (source field is empty)")

    if orphaned:
        print(f"\n{'─' * 72}")
        print(f"KEPT — no `{SAFE_TO_STRIP[args.field][0]}` to recompute from")
        for path in orphaned[:15]:
            print(f"  {path.parent.name}/{path.stem}")
        if len(orphaned) > 15:
            print(f"  … and {len(orphaned) - 15} more")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    for path, rendered in planned:
        tmp = path.with_suffix(".md.strip-tmp")
        tmp.write_text(rendered, encoding="utf-8")
        os.replace(tmp, path)

    print(f"STRIPPED `{args.field}` from {len(planned)} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
