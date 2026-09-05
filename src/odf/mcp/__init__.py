"""Optional MCP server. Not imported by ``odf/__init__.py``.

Importing ``odf.mcp.server`` pulls in the ``mcp``/uvicorn stack (the
``odf[mcp]`` extra), so it is only imported lazily by ``Project.start(mcp=True)``
— never eagerly by the core package.
"""
