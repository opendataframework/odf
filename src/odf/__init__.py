"""odf — CLI, MCP server, and UI for Open Data Framework.

Depends on ``opendataframework`` for the core framework. Submodules
(``odf.ui``, ``odf.mcp``, ``odf.chat``) pull in optional third-party
extras and are imported lazily by ``odf.server.Server.start()`` — never
eagerly here.
"""
