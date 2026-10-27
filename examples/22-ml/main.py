"""The `--template ml` project layout: runs, their params, per-step metrics
and artifacts, each kept in its own repository, so the UI, MCP and chat can
show and compare them with no extra code. Here, each run trains a real
scikit-learn classifier on handwritten digits.

On a fresh `app.db`, this script records a sweep by executing `task.sweep`
in-process, then trains one more run over MCP through `function.train.call`,
the way an MCP client would. Either way, it then finds the best run with
the `query_repository` MCP tool and exports it with `function.export-run.call`,
model included. Delete `app.db` to start over.
Run from this directory: `python main.py`.
"""

import asyncio
import json

import app  # noqa: F401 — registers the entities, repositories, functions, Sweep and RunComparison
from app.repositories import Runs
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True)

print(f"Topology UI running at {server.ui_url}")
print(f"MCP server running at {server.mcp_url}\n")

fresh = not server.context.get(Runs).all()
if fresh:
    for summary in server.context.execute("task.sweep"):
        print(f'context.execute("task.sweep") recorded {summary["run"]}: {summary["final"]}')
else:
    print("runs already recorded in app.db, skipping the sweep (delete app.db to start over)")


async def drive_via_mcp() -> None:
    """Connect to the running MCP server, train once if the database was
    fresh, then find and export the best run, the same way an external MCP
    client (e.g. Claude Desktop) would.
    """
    async with streamablehttp_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if fresh:
                result = await session.call_tool(
                    "function.train.call", {"learning_rate": 0.05, "epochs": 5}
                )
                summary = json.loads(result.content[0].text)
                print(f"function.train.call recorded {summary['run']}: {summary['final']}")

            result = await session.call_tool(
                "query_repository",
                {"key": "repository.artifacts", "limit": 500, "filters": {"name": "summary"}},
            )
            summaries = [a["content"] for a in json.loads(result.content[0].text)["records"]]
            best = min(summaries, key=lambda s: s["final"]["loss"])
            print(f"\nBest run, by final loss: {best['run']} {best['final']}")

            result = await session.call_tool("function.export-run.call", {"run_id": best["run_id"]})
            print(f"function.export-run.call exported it to {result.content[0].text}")


print("\nDriving the project over MCP, the same way an MCP client would:")
asyncio.run(drive_via_mcp())

server.stop()
