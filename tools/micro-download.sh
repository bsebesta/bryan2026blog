#!/usr/bin/env bash
#
# Download Micro.blog microposts into the vault (dock droplet 1).
#
# Pulls live from the Micropub API and writes each post into the Obsidian vault
# as a Source-tier micropost. It stops there — it does NOT export the site.
# Regenerating content/ and the homepage list is the job of the droplets that
# follow it (Prep, Serve, Commit all run export). Keeping this step to "download
# into Obsidian" matches the workflow order and avoids a redundant export.
#
# Occasional, not routine — run when there are new microposts to bring in. It is
# deliberately separate from Prep (vault hygiene) for that reason (PRODUCT.md
# §7.8, §12.3).
#
# Writes to the vault, so it shows a dry run and waits for confirmation.
#
# REQUIRES an app token in the environment (Account → App tokens on Micro.blog).
# Put `export MICROBLOG_TOKEN=…` in your shell profile so this droplet's
# terminal inherits it. The token never lives in the repo (RUNBOOK.md §3.1).

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PIPELINE_PY:-.venv/bin/python}"

if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
	echo "No virtualenv found. Run 'make setup' first."
	exit 1
fi

if [ -z "${MICROBLOG_TOKEN:-}" ]; then
	echo
	echo "  MICROBLOG_TOKEN is not set."
	echo
	echo "  1. Micro.blog → Account → App tokens → generate a token."
	echo "  2. Add to your shell profile (e.g. ~/.zshrc):"
	echo "       export MICROBLOG_TOKEN=your-token-here"
	echo "  3. Open a new terminal (or re-run this droplet) so it's picked up."
	echo
	read -n 1 -s -r -p "  Press any key to close."
	echo
	exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  DOWNLOAD MICROPOSTS — DRY RUN"
echo "  Pulling from the Micro.blog API. Nothing has been written yet."
echo "════════════════════════════════════════════════════════════════════════"

"$PY" -m pipeline.micro --from-api

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

"$PY" -m pipeline.micro --from-api --apply

echo
echo "  Microposts are in the vault. To publish them, run the next droplet —"
echo "  Prep Notes, Serve, or Commit (each re-exports the site)."
echo
read -n 1 -s -r -p "  Press any key to close."
echo
