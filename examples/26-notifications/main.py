"""Notifications: what components publish, shown as toasts in the UI.

The ``Counter`` service takes an order every few seconds through the
``take_order`` function, which publishes a notification for each one, and a
warning or an error when the pantry runs low or out. Each pops a notice in
every open tab of the UI. **Restock** (the ``Restock`` task) publishes a
success. ``Kitchen`` receives the tickets ``take_order`` publishes without a
summary, which the UI doesn't show.

Same boot as ``odf run``: build a Server from config and start(ui=True).
"""

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
