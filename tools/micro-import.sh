#!/usr/bin/env bash
#
# Import Micro.blog microposts into the vault, then re-export.
#
# Occasional, not routine. Unlike prep (vault hygiene run before every
# publish), this pulls posts from a Micro.blog export and is run only when
# there are new microposts to bring in. It is deliberately NOT part of prep for
# that reason — see PRODUCT.md §12.3.
#
# Like prep, every step writes to the vault, so the dry run is shown first and
# nothing is written without confirmation.
#
# BEFORE running: refresh the export. In the Micro.blog Mac app, File → Export →
# Markdown, and replace the contents of the vault's `_MICRO/` folder with it.
# The importer reads whatever is there now; it cannot fetch new posts itself.

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PIPELINE_PY:-.venv/bin/python}"

if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
	echo "No virtualenv found. Run 'make setup' first."
	exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  MICROPOST IMPORT — DRY RUN"
echo "  Reading the Micro.blog export. Nothing has been written yet."
echo "════════════════════════════════════════════════════════════════════════"

"$PY" -m pipeline.micro

echo
echo "════════════════════════════════════════════════════════════════════════"
read -r -p "  Write these microposts to the vault? [y/N] " reply
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

"$PY" -m pipeline.micro --apply

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  Regenerating site content and the homepage micropost list"
echo "════════════════════════════════════════════════════════════════════════"
"$PY" -m pipeline.export --apply

echo
echo "  Done. Commit when ready — or run the Commit Site droplet."
echo
read -n 1 -s -r -p "  Press any key to close."
echo
