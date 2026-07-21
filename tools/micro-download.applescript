-- Downloads Micro.blog microposts into the vault for bryansebesta.net (dock
-- droplet 1 of 4: Download → Prep → Serve → Commit).
--
-- Compile into an app with:
--   osacompile -o ~/Applications/bryansebesta.net/"1 Download Microposts.app" \
--       tools/micro-download.applescript
--
-- Prefers iTerm2, falls back to Terminal.app if it isn't installed.
--
-- Runs through a terminal deliberately. The script is interactive — it shows a
-- dry run and waits for confirmation before writing to the vault — so it needs
-- a real terminal, and a login shell so $MICROBLOG_TOKEN is in the environment.
-- Automator and Shortcuts cannot prompt and run with a minimal environment.

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
	set theTitle to "Download Microposts"

	-- The title is set from inside the shell, not just via AppleScript. iTerm
	-- lets the running program rename the session, so anything set externally
	-- is overwritten the moment the shell starts. This escape sequence is also
	-- terminal-agnostic — Terminal.app honours it too.
	set titleCmd to "printf '\\033]0;" & theTitle & "\\007'; "

	-- `; exit` ends the shell once the script finishes, so the window closes
	-- after the "press any key" pause rather than dropping to a prompt.
	runInTerminal(titleCmd & "cd " & repoPath & " && make micro-download; exit", theTitle)
end run
