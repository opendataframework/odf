"""Flat grid: the topology drawn as a top-down schematic.

config.toml's ``[ui] grid = "flat"`` swaps the isometric grid for a flat one:
every node a rounded square in its type's color, with its type's glyph on it.
This depot has one of each kind of node (repositories, a service, a task, a
pipeline and a function) so the glyphs sit side by side, and layout.json
gives the Couriers node a user glyph and a blue color, the way Customize
would.

Same boot as ``odf run``: build a Server from config and start(ui=True).
"""

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
