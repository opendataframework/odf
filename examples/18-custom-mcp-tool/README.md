# 18 — Custom MCP Tool

A `StockRoom` component implementing `opendataframework.component.McpToolsProtocol`'s
`mcp_tools()`, so `server.start(mcp=True)` registers its `low_stock` tool
as `stock-room.low_stock`, alongside the six fixed built-in tools
`odf.mcp.server.McpServer` always registers (`list_components`,
`query_repository`, `start_component`, `stop_component`, `execute_task`,
`component_logs`).

This isolates the concept covered in [`docs/index.md`](../../docs/index.md#mcp-server):
components aren't limited to the fixed generic surface — any resolved
component can add its own tools, detected structurally
(`isinstance(instance, McpToolsProtocol)`, never invoked by `Context`
itself) and namespaced `<kebab(ClassName)>.<tool name>` to avoid colliding
with the fixed tools or another component's own. Unlike
[`16-mcp-chat`](../16-mcp-chat) — whose `app/` is deliberately generic, so
it only demonstrates the fixed surface — `StockRoom` here is the one new
thing: a component whose own `mcp_tools()` returns something.

`low_stock` also shows why a custom tool earns its place instead of reusing
a fixed one: `execute_task()` takes no arguments at all, and
`query_repository()`'s `filters` are substring-only, so neither can express
"items at or below an explicit numeric threshold" — `low_stock(threshold:
int | None = None)` can, because it's a real typed parameter on a
purpose-built tool.

`Items` comes pre-seeded in-memory with three items, two already below
their reorder level (see `app/repositories.py`'s `_SEED_ITEMS`), so
`low_stock()` has something to report immediately.

## Structure

```
18-custom-mcp-tool/
├── README.md
├── config.toml
├── main.py               # entry point — starts mcp+ui, drives it via a real MCP client
└── app/
    ├── __init__.py       # imports all modules so decorators register at startup
    ├── entities.py       # Item(id, name, quantity, reorder_level) — @Entity
    ├── repositories.py   # Items — @Storage @Repository(Item), in-memory, pre-seeded
    └── components.py     # StockRoom — @Analytics @Component, implements mcp_tools()
```

## Dependencies

Needs the `mcp` extra (`pip install odf[mcp]`) for the MCP server and its
client, already in the repo's `dev` dependency group, so a plain
`poetry install` covers it (see [`CLAUDE.md`](../../CLAUDE.md)).

## Run it

```bash
cd examples/18-custom-mcp-tool
python main.py
```

Expected output (uvicorn/MCP request logging omitted for brevity):

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

Driving the project over MCP, the same way an MCP client would:
Tools exposed over MCP: ['list_components', 'query_repository', 'start_component', 'stop_component', 'execute_task', 'component_logs', 'stock-room.low_stock']

stock-room.low_stock()            -> [{"name": "Packing tape", "quantity": 4, "reorder_level": 10}, {"name": "Shipping labels", "quantity": 2, "reorder_level": 20}]
stock-room.low_stock(threshold=5) -> [{"name": "Packing tape", "quantity": 4, "reorder_level": 10}, {"name": "Shipping labels", "quantity": 2, "reorder_level": 20}]
```

Or start it via the CLI/UI:

```bash
odf run --mcp
```
