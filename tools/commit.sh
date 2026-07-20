#!/usr/bin/env bash
#
# Export from the vault, then review and commit.
#
# Export runs FIRST, before anything is shown, so its output appears in the
# diff you review rather than sneaking in behind it. Committing a stale
# content/ was the alternative — publishing a note in Obsidian and committing
# without exporting would have quietly left it off the site.
#
# Export never writes to the vault (that's `make prep`), so this only ever
# modifies files inside the repo.

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PIPELINE_PY:-.venv/bin/python}"

if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
	echo "No virtualenv found. Run 'make setup' first."
	exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  EXPORTING FROM VAULT"
echo "════════════════════════════════════════════════════════════════════════"

if ! "$PY" -m pipeline.export --apply; then
	echo
	echo "  Export failed — nothing committed."
	echo
	read -n 1 -s -r -p "  Press any key to close."
	echo
	exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  COMMIT"
echo "════════════════════════════════════════════════════════════════════════"
echo

if [ -z "$(git status --porcelain)" ]; then
	echo "  Nothing to commit — working tree is clean."
	echo
	read -n 1 -s -r -p "  Press any key to close."
	echo
	exit 0
fi

# Stage first so the summary below reflects everything, including new files.
# On abort the changes are left staged rather than reset — unstaging could
# undo something you staged deliberately.
git add -A

echo "  Changes to be committed:"
echo
git -c color.status=always status --short | sed 's/^/    /'
echo
git diff --cached --stat | sed 's/^/    /'

# GitHub rejects any file over 100MB outright and gets unhappy with repos past
# 1GB. Catching a stray large file here is much cheaper than rewriting history.
echo
big=""
while IFS= read -r f; do
	[ -f "$f" ] || continue
	sz=$(wc -c <"$f" | tr -d ' ')
	if [ "$sz" -gt 10485760 ]; then
		big="${big}    ${f}  ($((sz / 1048576)) MB)\n"
	fi
done < <(git diff --cached --name-only)

if [ -n "$big" ]; then
	echo "  ⚠ LARGE FILES STAGED — GitHub rejects anything over 100MB:"
	echo
	printf "%b" "$big"
	echo
fi

echo "════════════════════════════════════════════════════════════════════════"
read -r -p "  Commit message (empty to abort): " msg
echo

if [ -z "$msg" ]; then
	echo "  Aborted. Changes remain staged."
	echo
	read -n 1 -s -r -p "  Press any key to close."
	echo
	exit 0
fi

git commit -m "$msg"
echo

if git remote | grep -q .; then
	remote=$(git remote | head -1)
	branch=$(git rev-parse --abbrev-ref HEAD)
	read -r -p "  Push to ${remote}/${branch}? [y/N] " push_reply
	echo
	case "$push_reply" in
		[yY] | [yY][eE][sS])
			# Wrapped so a failed push doesn't trip `set -e` and skip the
			# pause below — the window would close before you could read the
			# error. The commit is already safe locally either way.
			if git push -u "$remote" "$branch"; then
				echo
				echo "  Pushed to ${remote}/${branch}."
			else
				echo
				echo "  ⚠ Push failed — the commit is saved locally."
				echo "    Fix the error above, then retry with:"
				echo "      git push -u ${remote} ${branch}"
			fi
			;;
		*)
			echo "  Not pushed. Commit is local."
			;;
	esac
else
	echo "  No remote configured — commit is local only."
	echo "  To add one:  git remote add origin <url>"
fi

echo
read -n 1 -s -r -p "  Press any key to close."
echo
