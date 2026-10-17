"""Functions: adopting plain functions with ``@Function``, called by key.

``to_eur`` and ``store_total`` in ``app/reports.py`` are plain functions
that only gained ``@Function``. Called directly they behave as before; called
through ``Context.call()`` their managed dependencies are injected, so the
caller passes only the rest. ``ReportTotals``, a ``@Task``, asks for
``store_total`` through ``Annotated`` and receives it already bound.

``server.start(mcp=True)`` also registers each function as its own MCP tool,
``<key>.call``, whose input schema leaves out the injected parameters. The
UI (``ui=True``) gives each function's node a **Call** action asking for the
same arguments. Run from this directory: ``python main.py``.
"""

import asyncio

import app  # noqa: F401 — registers Order/Orders/Rates/to_eur/store_total/ReportTotals
from app.components import Rates
from app.reports import to_eur
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}\n")

print(f'to_eur(100, "USD", Rates()) -> {to_eur(100, "USD", Rates())}  # direct: unchanged')
converted = server.context.call("function.to-eur", amount=100, currency="USD")
print(
    f'context.call("function.to-eur", amount=100, currency="USD") -> {converted}  # rates injected'
)
total = server.context.call("function.store-total", store="London")
print(f'context.call("function.store-total", store="London") -> {total}')
print(f'context.execute("task.report-totals") -> {server.context.execute("task.report-totals")}\n')


async def drive_via_mcp() -> None:
    """Connect to the running MCP server and call a function, the same way an
    external MCP client (e.g. Claude Desktop) would.
    """
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools exposed over MCP: {[t.name for t in tools.tools]}\n")

            schema = next(t for t in tools.tools if t.name == "function.store-total.call")
            print(f"function.store-total.call input schema: {schema.inputSchema['properties']}\n")

            result = await session.call_tool("function.store-total.call", {"store": "Berlin"})
            print(f'function.store-total.call(store="Berlin") -> {result.content[0].text}')


print("Driving the project over MCP, the same way an MCP client would:")
asyncio.run(drive_via_mcp())

server.stop()
