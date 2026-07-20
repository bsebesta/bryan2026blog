-- Launches the local Hugo dev server for bryansebesta.net.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/bryansebesta.net/"2 Serve Site.app" \
--       tools/serve-site.applescript
--
-- Prefers iTerm2, falls back to Terminal.app if it isn't installed.
--
-- Runs through a terminal deliberately. Automator and Shortcuts execute with a
-- minimal PATH that does not include Homebrew, so `hugo` would not be found.
-- A terminal opens a login shell with your normal environment, and the window
-- stays open so you can watch the build and stop it with Ctrl+C.

on runInTerminal(theCommand, theTitle)
	-- Checked on disk rather than via Finder: asking Finder to resolve a bundle
	-- id needs automation permission, and a denial looks identical to "not
	-- installed" — silently falling back to Terminal with no way to tell why.
	set hasITerm to (do shell script "if [ -d /Applications/iTerm.app ] || [ -d \"$HOME/Applications/iTerm.app\" ]; then echo yes; else echo no; fi") is "yes"

	-- `running` is checked BEFORE activate. Launching a terminal app opens a
	-- default window on its own; creating another unconditionally is what
	-- produced two windows on a cold start.
	if hasITerm then
		tell application "iTerm"
			set wasRunning to running
			activate
			if wasRunning then
				set targetWindow to (create window with default profile)
			else
				delay 0.4
				set targetWindow to current window
			end if
			tell current session of targetWindow
				set name to theTitle
				write text theCommand
			end tell
		end tell
	else
		tell application "Terminal"
			set wasRunning to running
			activate
			if wasRunning then
				set newTab to do script theCommand
			else
				delay 0.4
				set newTab to do script theCommand in front window
			end if
			set custom title of newTab to theTitle
		end tell
	end if
end runInTerminal

on run
	set repoPath to "$HOME/Sites/bryan2026blog-main"
	set theTitle to "Serve Site"

	-- The title is set from inside the shell, not just via AppleScript. iTerm
	-- lets the running program rename the session, so anything set externally
	-- is overwritten the moment the shell starts. This escape sequence is also
	-- terminal-agnostic — Terminal.app honours it too.
	set titleCmd to "printf '\\033]0;" & theTitle & "\\007'; "

	-- Deliberately NO `; exit` here, unlike Prep and Commit. The server runs
	-- until Ctrl+C, and if Hugo fails to start you need the error left on
	-- screen rather than a window that vanishes.
	runInTerminal(titleCmd & "cd " & repoPath & " && make serve", theTitle)

	-- Give Hugo a moment to bind the port before opening the browser.
	delay 3
	open location "http://localhost:1313/"
end run
