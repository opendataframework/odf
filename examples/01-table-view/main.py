"""Table view: the implicit default when a repository defines no data_view().

`odf run` is a thin CLI wrapper around building a Server from config and
calling start(ui=True). This script does the same two steps directly in
Python, to show that booting the UI isn't tied to the CLI — any process
can do it, e.g. to embed the UI in a larger application or a test fixture.

start() imports the `app` package for you by default (the same convention
`odf run`'s `--app` flag uses), registering its @Entity/@Repository
classes as a side effect — pass app_module= to point at a differently
named package, or app_module=None to register components yourself.

Books implements no data_view() at all, so the UI falls back to a plain
table, one row per record, one column per entity field, in declaration
order. See ../06-location-view for the same shape with data_view()
overridden to LocationView instead.
"""

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
