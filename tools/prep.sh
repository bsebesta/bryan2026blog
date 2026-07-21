#!/usr/bin/env bash
#
# Vault preprocessing: normalize, then stamp, then re-export.
#
# Every step here WRITES TO THE VAULT, so the script shows all dry runs first
# and requires explicit confirmation. A double-clickable icon that silently
# rewrote thousands of notes would undo the whole point of the dry-run design.
#
# Order matters: normalize before stamp, so `publish` values are clean before
# anything decides which notes are published.

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PIPELINE_PY:-.venv/bin/python}"

if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
	echo "No virtualenv found. Run 'make setup' first."
	exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  VAULT PREPROCESSING — DRY RUN"
echo "  Nothing has been written yet."
echo "════════════════════════════════════════════════════════════════════════"

"$PY" -m pipeline.seed
"$PY" -m pipeline.normalize
"$PY" -m pipeline.stamp

echo
echo "════════════════════════════════════════════════════════════════════════"
read -r -p "  Apply these changes to the vault? [y/N] " reply
echo

case "$reply" in
	[yY] | [yY][eE][sS]) ;;
	*)
		echo "  Aborted. Vault untouched."
		echo
		read -n 1 -s -r -p "  Press any key to close."
		echo
		exit 0
		;;
esac

# Seed first: a note with no `publish` gate can't be stamped or exported, so
# everything downstream depends on this having run.
"$PY" -m pipeline.seed --apply
"$PY" -m pipeline.normalize --apply
"$PY" -m pipeline.stamp --apply

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  Regenerating site content"
echo "════════════════════════════════════════════════════════════════════════"
"$PY" -m pipeline.export --apply

echo
echo "  Done. Commit when ready:"
echo "    cd ~/Sites/bryan2026blog-main && git add -A && git commit"
echo
read -n 1 -s -r -p "  Press any key to close."
echo
