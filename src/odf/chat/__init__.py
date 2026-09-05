"""Optional chat window. Not imported by ``odf/__init__.py``.

Importing ``odf.chat.engine`` pulls in the ``ollama`` client (the
``odf[chat]`` extra), so it is only imported lazily by
``Project.start(chat=True)`` — never eagerly by the core package.
"""
