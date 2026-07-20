-- Exports from the vault, then reviews and commits changes to the
-- bryansebesta.net repo.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/bryansebesta.net/"3 Commit Site.app" \
--       tools/commit-site.applescript
--
-- Prefers iTerm2, falls back to Terminal.app if it isn't installed.
--
-- Runs through a terminal because the script is interactive — it shows a diff
-- summary and prompts for a commit message before writing anything.

on runInTerminal(theCommand)
	-- Checked on disk rather than via Finder: asking Finder to resolve a bundle
	-- id needs automation permission, and a denial looks identical to "not
	-- installed" — silently falling back to Terminal with no way to tell why.
	set hasITerm to (do shell script "if [ -d /Applications/iTerm.app ] || [ -d \"$HOME/Applications/iTerm.app\" ]; then echo yes; else echo no; fi") is "yes"

	if hasITerm then
		tell application "iTerm"
			activate
			set newWindow to (create window with default profile)
			tell current session of newWindow
				write text theCommand
			end tell
		end tell
	else
		tell application "Terminal"
			activate
			do script theCommand
		end tell
	end if
end runInTerminal

on run
	set repoPath to "$HOME/Sites/bryan2026blog-main"
	runInTerminal("cd " & repoPath & " && make commit")
end run
