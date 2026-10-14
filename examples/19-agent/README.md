# 19 — Agent

A `Librarian` registered with `@Agent`: a class whose `invoke()` takes the
arguments of each call, here a `question: str` and an optional `limit: int`.
A `@Task`'s `execute()` takes none. The `Context` creates the agent and
injects its `Books` dependency like any other class, and calls it by key
through `context.call("agent.librarian", question=...)`, which logs the call.

`odf` exposes the agent in three places, each built from `invoke()`'s
signature:

- **UI**: the agent's node has an **Invoke** action. It opens a form with one
  field per argument, prefilled with the defaults, and shows the result under
  it. Values are converted to the annotated types before the call, so `limit`
  arrives as an `int`.
- **MCP**: the agent becomes its own tool, `agent.librarian.invoke`, namespaced like
  a component's `mcp_tools()`. The tool's input schema comes from the
  annotations and its description from the first paragraph of the class
  docstring, so a client is told exactly what to pass.
- **Chat**: `@agent.librarian` addresses the agent, keeping `agent.librarian.invoke`
  available for that message.

`invoke()` matches the words in the question against each book's title and
author, so the example runs offline. A real agent would hand the question to
a model at that point. The framework ships no model client, so the model is
usually another injected component.

## Structure

```
19-agent/
├── README.md
├── config.toml
├── main.py               # entry point: calls the agent, then drives it over MCP
└── app/
    ├── __init__.py       # imports all modules so decorators register at startup
    ├── entities.py       # Book(id, title, author, year) — @Entity
    ├── repositories.py   # Books — @Storage @Repository(Book), in-memory, pre-seeded
    └── agents.py         # Librarian — @Analytics @Agent, invoke(question, limit=3)
```

## Dependencies

Needs the `mcp` extra (`pip install odf[mcp]`) for the MCP server and its
client. It is already in the repo's `dev` dependency group, so a plain
`poetry install` covers it.

## Run it

```bash
cd examples/19-agent
python main.py
```

Expected output:

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

context.call("agent.librarian", question="Anything by Le Guin?") -> [{'title': 'A Wizard of Earthsea', 'author': 'Ursula K. Le Guin', 'year': 1968}, {'title': 'The Left Hand of Darkness', 'author': 'Ursula K. Le Guin', 'year': 1969}]

Driving the project over MCP, the same way an MCP client would:
Tools exposed over MCP: ['list_components', 'query_repository', 'start_component', 'stop_component', 'execute_task', 'component_logs', 'agent.librarian.invoke']

agent.librarian.invoke input schema: {'question': {'title': 'Question', 'type': 'string'}, 'limit': {'default': 3, 'title': 'Limit', 'type': 'integer'}}

agent.librarian.invoke(question=..., limit=1) -> {
  "title": "Dune",
  "author": "Frank Herbert",
  "year": 1965
}
```

Or start it with the CLI and invoke `Librarian` from the UI:

```bash
odf run --mcp
```
