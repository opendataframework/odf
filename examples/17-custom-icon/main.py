"""Custom topology icon: extending the dev UI's icon picker beyond the
six built-in exec-type defaults.

`odf run` is a thin CLI wrapper around building a Server from config and
calling start(ui=True). This script does the same two steps directly in
Python, like ../01-table-view/main.py.

This project's config.toml registers `icons/lighthouse.js` under
`[ui] icon-scripts` — a plain JS file defining a draw function with the
same `(sx, sy, accent, lit)` signature as every built-in icon, calling
`ODF.registerIcon("lighthouse", drawLighthouse, meta)` at load time (see
that file for the drawing code). Server.start(ui=True) below picks it up
from config automatically and serves it to the browser; a
framework-extension package would instead call
`odf.ui.extensions.register_icon_script()` at import time, so every
project using it gets the icon without any config.toml change.

`config.toml` also registers two named colors under `[ui.colors]`, and
`layout.json` pre-seeds Beacons' icon/color override — so Beacons already
renders with the lighthouse tower in amber the moment the UI loads. Click
it, then "Customize", to see both swatches highlighted in their pickers
alongside the built-ins. Run `odf run` instead of this script to try the
same thing through the CLI.
"""

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Beacons already shows the lighthouse icon/color — click it, then Customize")
print("Press Ctrl+C to stop")

server.wait()
