"""Deploy: the UI and MCP server behind Traefik, with HTTPS and a login.

The project itself is small, a Notebooks repository like 21-notebook-view's;
the point is compose.yaml and traefik/, which put it behind a reverse proxy.
`docker compose up` runs `odf run` in one container with Traefik in front of
it, reached at https://localhost.

Run from this directory without Docker: `python main.py`, or `odf run`.
"""

from app.repositories import Notebooks

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

notebooks = server.context.get(Notebooks)

print("All notebooks:")
for notebook in notebooks.all():
    print(f"  Notebook(name={notebook.name!r}, content=<{len(notebook.content)} bytes>)")

server.stop()
