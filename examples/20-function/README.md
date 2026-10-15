# 20 — Function

Adopting a codebase of plain functions without rewriting it into classes.
`app/reports.py` holds two reporting functions as they were written,
`to_eur(amount, currency, rates)` and `store_total(store, orders, convert)`,
and each only gains `@Function`, with a layer on top for `store_total`.

Their bodies and signatures are unchanged, so a direct call still takes every
argument, as before, and their tests need no framework. Called through the
`Context` instead, a parameter whose type the `Context` manages is injected:

- `rates: Rates` and `orders: Orders` are a component and a repository, so
  `context.call("function.to-eur", amount=100, currency="USD")` passes only the
  amount and the currency.
- `convert: Annotated[Callable[..., float], to_eur]` asks for another function
  by naming it in `Annotated`, and receives `to_eur` with `rates` already
  filled in.

New code can ask for an adopted function in the same way. `ReportTotals`, a
`@Task`, takes `total: Annotated[Callable[..., float], store_total]` in its
constructor, so `self.total("Berlin")` passes only the store.

`odf` shows each function in three places, all built from its signature less
the injected parameters:

- **UI**: each function is a node, linked to what is injected into it and to
  what asks for it. Its **Call** action opens a form with one field per
  argument it takes, and shows the result under it.
- **MCP**: each function becomes its own tool, `function.to-eur.call` and
  `function.store-total.call`. The tool's input schema comes from the
  annotations and its description from the first paragraph of the docstring.
- **Chat**: `@function.store-total` addresses the function, keeping
  `function.store-total.call` available for that message.

Every call through the `Context` is logged to the function's log, which its
node's **Show Logs** action and the `component_logs` MCP tool read.

## Structure

```
20-function/
├── README.md
├── config.toml
├── main.py               # entry point: calls the functions, then drives them over MCP
└── app/
    ├── __init__.py       # imports all modules so decorators register at startup
    ├── entities.py       # Order(id, store, amount, currency) — @Entity
    ├── repositories.py   # Orders — @Storage @Repository(Order), in-memory, pre-seeded
    ├── components.py     # Rates — @Component, fixed exchange rates to euros
    ├── reports.py        # to_eur, store_total — the adopted @Function functions
    └── tasks.py          # ReportTotals — @Analytics @Task built on store_total
```

## Dependencies

Needs the `mcp` extra (`pip install odf[mcp]`) for the MCP server and its
client. It is already in the repo's `dev` dependency group, so a plain
`poetry install` covers it.

## Run it

```bash
cd examples/20-function
python main.py
```

Expected output:

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

to_eur(100, "USD", Rates()) -> 90.0  # direct: unchanged
context.call("function.to-eur", amount=100, currency="USD") -> 90.0  # rates injected
context.call("function.store-total", store="London") -> 240.0
context.execute("task.report-totals") -> {'Berlin': 192.0, 'Lisbon': 40.0, 'London': 240.0}

Driving the project over MCP, the same way an MCP client would:
Tools exposed over MCP: ['list_components', 'query_repository', 'start_component', 'stop_component', 'execute_task', 'component_logs', 'function.store-total.call', 'function.to-eur.call']

function.store-total.call input schema: {'store': {'title': 'Store', 'type': 'string'}}

function.store-total.call(store="Berlin") -> 192.0
```

Or start it with the CLI and call `store_total` from the UI:

```bash
odf run --mcp
```
