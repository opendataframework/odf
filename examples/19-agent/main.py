"""Agents: an ``@Agent`` class whose ``invoke()`` takes arguments, called by key.

``Librarian`` is resolved like any other class, with ``Books`` injected
through its constructor, and called through ``Context.call()``. On top of
that, ``server.start(mcp=True)`` registers it as its own MCP tool,
``agent.librarian.invoke``, whose input schema is ``invoke()``'s signature, so a
client is told it takes a ``question: str`` and an optional ``limit: int``.

Also starts the UI (``ui=True``), where ``Librarian``'s **Invoke** action asks
for the same arguments in a form. Run from this directory: ``python main.py``.
"""

import asyncio

import app  # noqa: F401 — registers Book/Books/Librarian
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}\n")

answer = server.context.call("agent.librarian", question="Anything by Le Guin?")
print(f'context.call("agent.librarian", question="Anything by Le Guin?") -> {answer}\n')


async def drive_via_mcp() -> None:
    """Connect to the running MCP server and invoke the agent, the same way an
    external MCP client (e.g. Claude Desktop) would.
    """
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools exposed over MCP: {[t.name for t in tools.tools]}\n")

            schema = next(t for t in tools.tools if t.name == "agent.librarian.invoke").inputSchema
            print(f"agent.librarian.invoke input schema: {schema['properties']}\n")

            result = await session.call_tool(
                "agent.librarian.invoke", {"question": "Anything by Herbert?", "limit": 1}
            )
            print(f"agent.librarian.invoke(question=..., limit=1) -> {result.content[0].text}")


print("Driving the project over MCP, the same way an MCP client would:")
asyncio.run(drive_via_mcp())

server.stop()
