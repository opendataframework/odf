"""View: notebooks in a DocumentView, edited in place in Jupyter.

Notebooks implements data_view() -> DocumentView over the .ipynb files in
notebooks/. The topology UI renders a card per notebook; selecting one shows
its cells and their saved outputs. With the notebook package installed, the
pencil in the reader's rail opens the notebook in Jupyter, embedded in the
reader, with a kernel running in this directory. Jupyter saves through
Notebooks.save(), which writes the file back.

Run from this directory: `python main.py`, or `odf run` and click
"View Documents" on Notebooks in the UI.
"""

from app.repositories import Notebooks

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

notebooks = server.context.get(Notebooks)

print("All notebooks:")
for notebook in notebooks.all():
    print(f"  Notebook(name={notebook.name!r}, content=<{len(notebook.content)} bytes>)")

print(f"\ndata_view() -> {notebooks.data_view()}")

server.stop()
