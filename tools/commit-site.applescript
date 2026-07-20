-- Reviews and commits changes to the bryansebesta.net repo.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/"Commit Site.app" tools/commit-site.applescript
--
-- Runs through Terminal because the script is interactive — it shows a diff
-- summary and prompts for a commit message before writing anything.

on run
	set repoPath to "$HOME/Sites/bryan2026blog-main"

	tell application "Terminal"
		activate
		do script "cd " & repoPath & " && make commit"
	end tell
end run
