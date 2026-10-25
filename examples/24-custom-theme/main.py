"""Custom UI theme: a project serving its own pixel-art theme instead of a
built-in one.

`odf run` is a thin CLI wrapper around building a Server from config and
calling start(ui=True). This script does the same two steps directly in
Python, like ../01-table-view/main.py.

This project's config.toml sets `[ui] theme = "./pixel-theme"`, a path
rather than a built-in theme's name, so Server.start(ui=True) below serves
that directory's `theme.css`, `theme.js` and `favicon.svg` (see that
directory for the theme itself). Run `odf run` instead of this script to
try the same thing through the CLI, or `odf run --theme default` to compare
it with a built-in theme.
"""

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
