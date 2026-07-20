-- Runs vault preprocessing for bryansebesta.net: normalize, stamp, re-export.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/"Prep Site Notes.app" tools/prep-notes.applescript
--
-- Prefers iTerm2, falls back to Terminal.app if it isn't installed.
--
-- Runs through a terminal deliberately. The script is interactive — it shows
-- dry runs and waits for confirmation before writing to the vault — so it needs
-- a real terminal. Automator and Shortcuts cannot prompt, and would either hang
-- or write without asking.

on runInTerminal(theCommand)
	set hasITerm to false
	try
		tell application "Finder" to get application file id "com.googlecode.iterm2"
		set hasITerm to true
	end try

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
	runInTerminal("cd " & repoPath & " && make prep")
end run
