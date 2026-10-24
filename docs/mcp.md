# MCP Server

Exposes the same actions available in the UI (service start/stop,
task/pipeline execution, agent invocation, function calls, log inspection,
repository data queries) as [MCP](https://modelcontextprotocol.io) tools for
any MCP-speaking client.

```bash
pip install "odf[mcp]"
odf run --mcp
```

```python
server.start(mcp=True)
print(server.mcp_url)  # http://127.0.0.1:4748/mcp
```

The server speaks the streamable HTTP transport and binds to
`--mcp-host`/`--mcp-port` (`127.0.0.1:4748` by default). It has no login,
and a reverse proxy in front of the UI doesn't cover it (see
[Deploying](ui.md#mcp)), so keep it on `127.0.0.1`.

## Connecting a client

Point the client at the URL `odf run` prints. For example, with Claude Code:

```bash
claude mcp add --transport http my-project http://127.0.0.1:4748/mcp
```

The [chat window](chat.md) uses the same tools in-process, with no client to
configure.

## Tools

Each tool takes a component's key, `<namespace>.<name>`, as its `key` argument
(`start_component(key="service.postgres")`), and `list_components` returns it
as each entry's `id`.

| Tool | Arguments | Does |
|---|---|---|
| `list_components` | — | Lists every resolved component, repository, service, task, pipeline, agent and function: its `id`, type, layer and, for a service, whether it is running |
| `query_repository` | `key`, `limit=50`, `offset=0`, `filters=None` | Returns `{"records": [...], "total": n}`, a page of a repository's records. `filters` maps field names to case-insensitive substrings; `limit` is capped at 500 |
| `start_component` | `key` | Starts a `@Service`; a no-op if it is running |
| `stop_component` | `key` | Stops a `@Service`; a no-op if it is stopped |
| `execute_task` | `key` | Executes a `@Task` or `@Pipeline` and returns what `execute()` returns |
| `component_logs` | `key`, `lines=50` | Returns the last log entries of any component |

On top of these six, a project adds its own tools, each prefixed by its key.

### Agents and functions

Each resolved `@Agent` becomes its own tool, `<key>.invoke` (`agent.librarian.invoke`).
Its input schema is `invoke()`'s signature and
its description is the first paragraph of the class docstring, so a client
is told what the agent takes rather than guessing at a generic `arguments`
object. The tool calls the agent through `context.call()`, which logs the call
to the agent's log. `list_components` lists agents with the type `agent`. An
argument that can't be passed by keyword (positional-only, `*args`,
`**kwargs`) is left out of the schema. See
[`examples/19-agent`](https://github.com/opendataframework/odf/tree/main/examples/19-agent).

Each resolved `@Function` becomes its own tool the same way, `<key>.call`
(`function.load-data.call`). Its input schema is the function's signature,
less the parameters the `Context` injects, and its description is the first
paragraph of the function's docstring. `list_components` lists functions with
the type `function`, and gives every entry a `verb`, `invoke` or `call`, when
it has one of these tools. See
[`examples/20-function`](https://github.com/opendataframework/odf/tree/main/examples/20-function).

### A component's own tools

Any resolved component can contribute its own tools by implementing
`opendataframework.component.McpToolsProtocol`'s `mcp_tools()`. They are prefixed
by the component's key, so a `@Component class StockRoom`'s `low_stock` tool is
`component.stock-room.low_stock`. Two tools with the same full name raise a
`ValueError` at start.

An `McpTool` needs a non-empty `description` and a fully typed handler: every
parameter annotated, a return annotation (`-> None` counts), no
`*args`/`**kwargs`, a method or function rather than a lambda, and no
`from __future__ import annotations` in its module. The MCP server passes the
description and the handler's signature to the client as the tool's
description and input schema, which is all a model sees of the tool.
`opendataframework` raises when a tool doesn't meet this, and `odf run`
reports it as a start-up error. See
[`examples/18-custom-mcp-tool`](https://github.com/opendataframework/odf/tree/main/examples/18-custom-mcp-tool).
