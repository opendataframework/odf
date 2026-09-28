"""Component-exposed MCP tools: a component's own ``mcp_tools()`` adds tools
beyond the six fixed built-ins ``odf.mcp.server.McpServer`` always registers.

``server.start(mcp=True)`` (mirrors ../16-mcp-chat/main.py) exposes the
resolved Context over MCP: the six fixed tools (``list_components``,
``query_repository``, ``start_component``, ``stop_component``,
``execute_task``, ``component_logs``), plus, for every resolved component
implementing ``opendataframework.component.McpToolsProtocol``, that
component's own ``mcp_tools()`` entries — namespaced
``<kebab(ClassName)>.<tool name>``. Here, ``StockRoom.low_stock`` shows up
as ``stock-room.low_stock``.

``execute_task()`` takes no arguments and ``query_repository()``'s filters
are substring-only — neither can express "items at or below an explicit
numeric threshold" as cleanly as a purpose-built tool with its own typed
parameter. That's the one thing this example isolates; see
``app/components.py``'s ``StockRoom`` for the ``mcp_tools()``
implementation.

Also starts the UI (``ui=True``) so ``StockRoom``/``Items`` are browsable,
same as ../16-mcp-chat. Run from this directory: ``python main.py``.
"""

import asyncio

import app  # noqa: F401 — registers Items/StockRoom
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}\n")


async def drive_via_mcp() -> None:
    """Connect to the running MCP server and call the custom tool, the same
    way an external MCP client (e.g. Claude Desktop) would.
    """
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools exposed over MCP: {[t.name for t in tools.tools]}\n")

            result = await session.call_tool("stock-room.low_stock", {})
            print(f"stock-room.low_stock()            -> {result.content[0].text}")

            result = await session.call_tool("stock-room.low_stock", {"threshold": 5})
            print(f"stock-room.low_stock(threshold=5) -> {result.content[0].text}")


print("Driving the project over MCP, the same way an MCP client would:")
asyncio.run(drive_via_mcp())

server.stop()
