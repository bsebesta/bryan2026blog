-- Runs vault preprocessing for bryansebesta.net: normalize, stamp, re-export.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/"Prep Site Notes.app" tools/prep-notes.applescript
--
-- Runs through Terminal deliberately. The script is interactive — it shows dry
-- runs and waits for confirmation before writing to the vault — so it needs a
-- real terminal. Automator and Shortcuts cannot prompt, and would either hang
-- or write without asking.

on run
	set repoPath to "$HOME/Sites/bryan2026blog-main"

	tell application "Terminal"
		activate
		do script "cd " & repoPath & " && make prep"
	end tell
end run
