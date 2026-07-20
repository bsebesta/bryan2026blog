#!/usr/bin/env bash
#
# Review and commit changes to the site repo.
#
# Purely a git operation — it does not export. Run `make apply` (or the Serve
# or Prep launchers, both of which export) first if you've published new notes,
# or content/ will be stale relative to the vault.

set -euo pipefail
cd "$(dirname "$0")/.."

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
			git push "$remote" "$branch"
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
