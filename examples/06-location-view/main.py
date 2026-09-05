"""Location view: data_view() picks the UI's viewer for a repository.

Stores implements LocationView instead of the default table — the UI
renders a map with one marker per record instead of a grid of columns by
default, with a one-click toggle back to a plain table.

Stores comes pre-seeded in-memory (see app/repositories.py's _SEED_STORES)
rather than seeded here, so there's a handful of real locations to look at
on the map without hand-typing coordinates — main.py only reads them back.
Run from this directory: `python main.py` or `odf run`.
"""

from app.repositories import Stores

from odf.server import Server

server = Server.from_config("config.toml")  # wires Stores via DI
server.start()

stores = server.context.get(Stores)

print("All stores:")
for store in stores.all():
    print(f"  {store}")

# what the UI calls to decide it should render a map instead of a table
print(f"\ndata_view() -> {stores.data_view()}")

server.stop()
