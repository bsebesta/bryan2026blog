-- Launches the local Hugo dev server for bryansebesta.net.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/"Serve Site.app" tools/serve-site.applescript
--
-- Prefers iTerm2, falls back to Terminal.app if it isn't installed.
--
-- Runs through a terminal deliberately. Automator and Shortcuts execute with a
-- minimal PATH that does not include Homebrew, so `hugo` would not be found.
-- A terminal opens a login shell with your normal environment, and the window
-- stays open so you can watch the build and stop it with Ctrl+C.

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
	runInTerminal("cd " & repoPath & " && make serve")

	-- Give Hugo a moment to bind the port before opening the browser.
	delay 3
	open location "http://localhost:1313/"
end run
