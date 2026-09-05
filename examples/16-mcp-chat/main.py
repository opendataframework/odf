"""MCP + chat: `server.start(mcp=True, chat=True)` exposes the resolved
Context as MCP tools — list_components, start_component, stop_component,
execute_task, component_logs — over streamable HTTP, the same tools any
MCP-speaking client (Claude Desktop, an agent, or the dev UI's own chat
window) can call to drive the project instead of clicking through the
topology UI.

This isolates the concept covered in `docs/chat.md`: chat is not its own
capability, it is a local Ollama model wired to the *same* FastMCP instance
the MCP server serves — mcp=True is what gives it something to act on. The
ui=/mcp=/chat= orchestration itself lives on `odf.server.Server`, which
wraps a plain `opendataframework.Project` — see this package's `CLAUDE.md`.

main.py drives the MCP server itself over the real streamable-HTTP
transport, using the `mcp` package's own client — exactly what Claude
Desktop or any other MCP client does, no external process required. The
chat window needs `ollama serve` running locally with a pulled tool-calling
model; see README for trying that from the dev UI instead.

Tickets comes pre-seeded in-memory (see app/repositories.py's
_SEED_TICKETS) rather than seeded here, so there's already something for
TriageTickets/the MCP tools/the chat model to act on. Run from this
directory: `python main.py`.
"""

import asyncio

import app  # noqa: F401 — registers Tickets/TriageTickets/Watchdog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True, chat=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}")
print(
    "Chat window: open the topology UI above — needs `ollama serve` running "
    "locally with `ollama pull gpt-oss:20b`\n"
)


async def drive_via_mcp() -> None:
    """Connect to the running MCP server and call a few of its tools,
    the same way an external MCP client (e.g. Claude Desktop) would.
    """
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools exposed over MCP: {[t.name for t in tools.tools]}\n")

            result = await session.call_tool("execute_task", {"name": "TriageTickets"})
            print(f"execute_task(TriageTickets) -> {result.content[0].text}")

            result = await session.call_tool("stop_component", {"name": "Watchdog"})
            print(f"stop_component(Watchdog)    -> {result.content[0].text}")

            result = await session.call_tool("start_component", {"name": "Watchdog"})
            print(f"start_component(Watchdog)   -> {result.content[0].text}")


print("Driving the project over MCP, the same way an MCP client would:")
asyncio.run(drive_via_mcp())

server.stop()
