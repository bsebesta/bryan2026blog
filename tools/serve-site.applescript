-- Launches the local Hugo dev server for bryansebesta.net.
--
-- Compile into an app with:
--   osacompile -o ~/Applications/"Personal Site.app" tools/serve-site.applescript
--
-- Runs through Terminal deliberately. Automator and Shortcuts execute with a
-- minimal PATH that does not include Homebrew, so `hugo` would not be found.
-- Terminal opens a login shell with your normal environment.
--
-- The window stays open so you can watch the build and stop it with Ctrl+C.

on run
	set repoPath to "$HOME/Sites/bryan2026blog-main"

	tell application "Terminal"
		activate
		do script "cd " & repoPath & " && make serve"
	end tell

	-- Give Hugo a moment to bind the port before opening the browser.
	delay 3
	open location "http://localhost:1313/"
end run
