# 16 — MCP + Chat

A `Tickets` repository, a `TriageTickets` `@Analytics @Task`, and a
`Watchdog` `@Service` — three ordinary components, nothing new about them.
What's new is starting the `odf.server.Server` with `server.start(ui=True,
mcp=True, chat=True)`: the same resolved `Context` that backs the topology
UI gets exposed as MCP tools (`list_components`, `start_component`,
`stop_component`, `execute_task`, `component_logs`) over streamable HTTP,
and the dev UI's chat window is a local Ollama model wired to those same
tools in-process.

This isolates the concept covered in [`docs/chat.md`](../../docs/chat.md):
chat is not its own capability, it's a thin conversational layer over
whatever `mcp=True` already exposes — pass `chat=True` without `mcp=True`
and the model still replies, it just can't act on the project. `mcp`/`chat`
are deliberately generic: they introspect any `Context`, so nothing in
`app/` here is MCP- or chat-specific — the same three-component shape from
`opendataframework`'s `examples/04-task-and-pipeline/` would work
identically.

`main.py` drives the MCP server itself, over the real streamable-HTTP
transport, using the `mcp` package's own client — the same protocol Claude
Desktop or any other MCP-speaking client uses, so no external process is
needed to see it work. The chat window needs a local Ollama daemon and is
only demonstrated via the dev UI, not `main.py` — see below.

`Tickets` comes pre-seeded in-memory with three tickets (see
`app/repositories.py`'s `_SEED_TICKETS`) — there's no reason to reach for
a file when the data is this small, and there needs to be something real
for `TriageTickets`, the MCP tools, and the chat model to act on.

## Structure

```
16-mcp-chat/
├── config.toml          # watchdog tick interval, [project.chat] model/host
├── main.py               # entry point — starts mcp+chat, drives it via a real MCP client
└── app/
    ├── __init__.py       # imports all modules so decorators register at startup
    ├── entities.py        # Ticket(id, subject, status) — @Entity
    ├── repositories.py    # Tickets — @Storage @Repository(Ticket), in-memory, pre-seeded
    ├── tasks.py            # TriageTickets — @Analytics @Task, counts open/closed
    └── services.py         # Watchdog — @Service, ticks in the background
```

## Dependencies

Needs the `mcp` extra (`pip install odf[mcp]`) for the MCP server and its
client, already in the repo's `dev` dependency group, so a plain
`poetry install` covers it (see [`CLAUDE.md`](../../CLAUDE.md)). Trying the
chat window additionally needs the `chat` extra (`pip install odf[chat]`,
also already in `dev`) plus a running [Ollama](https://ollama.com) daemon —
see below.

## Run it

```bash
cd examples/16-mcp-chat
python main.py
```

Expected output (uvicorn/MCP request logging omitted for brevity; the
`Watchdog.*` lines interleave with it as the background service starts,
stops, and restarts):

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp
Chat window: open the topology UI above — needs `ollama serve` running locally with `ollama pull gpt-oss:20b`

Driving the project over MCP, the same way an MCP client would:
Tools exposed over MCP: ['list_components', 'start_component', 'stop_component', 'execute_task', 'component_logs']

execute_task(TriageTickets) -> {
  "total": 3,
  "open": 2,
  "closed": 1
}
stop_component(Watchdog)    -> Watchdog stopped
start_component(Watchdog)   -> Watchdog started
```

Or start the dev UI, which starts both the MCP server and the chat window:

```bash
odf run --mcp --chat
```

To try the chat window for real:

1. Install and run [Ollama](https://ollama.com) locally: `ollama serve`.
2. Pull a tool-calling-capable model: `ollama pull gpt-oss:20b`.
3. Open the topology UI and ask it to triage the tickets or stop the
   watchdog — it calls the same `execute_task`/`stop_component` tools
   `main.py` calls directly above, just from a conversational turn instead
   of a script.

Without Ollama running, the chat window shows an inline error rather than
hanging — `mcp=True`/`chat=True` themselves need no external daemon, only
the chat *model* does.
