"""Built-in UI. Not imported by ``odf/__init__.py``.

Importing ``odf.ui.server`` pulls in FastAPI/uvicorn (the ``odf[ui]`` extra),
so it is only imported lazily by ``Project.start(ui=True)`` — never eagerly
by the core package.
"""
