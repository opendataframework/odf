"""Channels: a help desk's conversations in the chat, with a ticket as a card.

``Messages`` and ``Tickets`` (``app/repositories.py``) both declare a
``conversation()`` in the ``support`` channel: messages on their sides, one
thread per customer, and each ticket a card in its customer's thread.
``send_reply`` (``app/functions.py``) takes ``Annotated[int,
Record(Tickets)]``, so it's the card's action.

This drives it over MCP, as another client would: ``list_channels``,
``read_thread``, then the card's action through its own tool. Open the UI's
**Chat** to see the same thread. Run from this directory: ``python main.py``.
"""

import asyncio
import json

import app  # noqa: F401 — registers Message/Ticket/Messages/Tickets/send_reply
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}\n")


def _data(result):
    """Unwrap a structured tool result."""
    return result.structuredContent["result"]


async def drive_via_mcp() -> None:
    """Read the support channel, then send a ticket's reply, edited first."""
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            (channel,) = _data(await session.call_tool("list_channels", {}))
            threads = [t["thread"] for t in channel["threads"]]
            print(f"Channel {channel['name']!r}, threads: {threads}")

            args = {"channel": "support", "thread": "Ada"}
            items = _data(await session.call_tool("read_thread", args))
            for item in items:
                side = item.get("direction") or "card"
                print(f"  [{side}] {item['text'].splitlines()[0]}")

            card = next(i for i in items if i["kind"] == "card")
            (action,) = card["actions"]
            tool = f"{action['id']}.{action['verb']}"
            print(f"\nThe card's action: {tool}({action['param']}={action['value']})")
            print(f"  filled in from the ticket: {json.dumps(action['prefill'])}")

            edited = "So sorry, Ada! A new one goes out by express today, on us."
            result = await session.call_tool(
                tool, {action["param"]: action["value"], "reply": edited}
            )
            print(f"  sent: {result.content[0].text}\n")

            items = _data(await session.call_tool("read_thread", args))
            print(f"Ada's thread now ends: [{items[-1]['direction']}] {items[-1]['text']}")


asyncio.run(drive_via_mcp())

server.stop()
