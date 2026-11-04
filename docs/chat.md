# Chat

An optional chat window in the UI, backed by a local [Ollama](https://ollama.com)
model. It can act on the project by calling the same tools the MCP server
(see [MCP Server](mcp.md)) exposes — start/stop services, execute tasks
and pipelines, query repositories, inspect logs — so you can drive the project conversationally
instead of clicking through the UI.

Like the UI and MCP server, chat is not a DI-managed `Component` —
it is started directly by `Server.start()` and requires an optional extra.

## Enabling

```bash
pip install "odf[ui,mcp,chat]"
```

```python
server = Server.from_config("config.toml")
server.start(ui=True, mcp=True, chat=True)
```

`chat=True` requires `ui=True` — the chat window is served by the topology
UI, on the same host/port, not a separate server. Passing `chat=True`
without `ui=True` raises `ValueError`.

`mcp=True` is optional but recommended: without it, chat still answers
questions as a plain LLM, but has no tool-calling access to the project (no
starting/stopping components, no running tasks).

## Configuration

Connection parameters for the local Ollama daemon come from `[project.chat]`
in config — not from a `start()` kwarg, since these are the kind of
per-environment values that belong in `config.toml`:

```toml
[project.chat]
model = "gpt-oss:20b"
ollama-host = "http://localhost:11434"
debug = false
context-length = 32768
```

| Key | Default | Description |
|---|---|---|
| `model` | `"gpt-oss:20b"` | Ollama model name. Must already be pulled (`ollama pull gpt-oss:20b`). |
| `ollama-host` | `"http://localhost:11434"` | URL of the running Ollama daemon (`ollama serve`). |
| `debug` | `false` | Show tool-call/tool-result debug info inline in the chat window. |
| `context-length` | Ollama's default | The model's context window in tokens, sent as Ollama's `num_ctx`. Raise it once a project has many tools (see below). |
| `system-prompt` | built in | What the model is told first in a turn that has tools (see below). `""` sends none. |

### Context length

Every turn offers the model every tool's name, description and argument
schema, and `list_components` returns every node of the project. In a project
with a couple of dozen components that's over ten thousand tokens, and
when it no longer fits Ollama's default window, the oldest part of the turn
(the question itself) falls out of it, and the model answers something else.
Set `context-length` to a window that holds it; 32768 is plenty for a few
dozen tools, at the cost of more memory on the Ollama host.

### System prompt

Unless the conversation brings its own system message, a turn with tools
starts with a short one: answer from what the tools returned in this
conversation, and say so when they don't show something, rather than adding
records or activity they didn't show; answer in plain words or a short
table, not the tools' raw output; and start, stop, run, invoke or import
something only when asked. Small local models need saying it. Set
`system-prompt` to replace it with your own, such as one naming the
project's domain.

## How tool-calling works

When `mcp=True` is also passed, `Server.start()` hands the chat engine a
reference to the same `FastMCP` instance the MCP server serves over
streamable HTTP (`McpServer.mcp`) — tool definitions and execution are
shared in-process, not duplicated. On each turn, the model is offered the
current tool list — the seven [fixed tools](mcp.md#tools) (`list_components`,
`query_repository`, `start_component`, `stop_component`, `execute_task` for a
task or pipeline, `component_logs`, `recent_notifications`) plus, for every resolved component that exposes its own
MCP tools (prefixed by its key, `<namespace>.<name>.<tool>`), that
component's own tools, for every resolved `@Agent` its `<key>.invoke` tool, and
for every resolved `@Function` its `<key>.call` tool;
these are dynamic per project, so they aren't enumerated here by name. If
the model requests a tool call, it's always executed and its result fed
back to the model for a follow-up reply; the chat window additionally
shows what was called and its result inline only when `[project.chat]`'s
`debug` is `true`.

A model sometimes gets a tool's name slightly wrong: `function_margins` or
`margins_call` for `function.margins.call`. Ignoring case, dots, dashes and
underscores, a name that matches exactly one tool, as the whole name, its
start or a part of it, calls that tool. Otherwise the model is told there's
no such tool, along with the closest names, and can try again.

## Addressing a component with `@`

Mentioning a component's key, `@<namespace>.<name>`, anywhere in a message
scopes that turn's tool access to just that component — its own exposed
tools (for an `@Agent`, its `<key>.invoke`, and for an `@Function`, its
`<key>.call`), its own repository data (if it's a `Repository`), and
its own lifecycle actions and what it announced
(`start_component`/`stop_component`/`execute_task`/`component_logs`/`recent_notifications`,
forced to that component regardless of what the model passes) — instead
of offering every tool in the project. This is useful once a project has
several repositories/services: instead of the model guessing which
repository a data question is about, `@repository.users how many rows are
there?` scopes `query_repository` to just that repository's data, and
`@agent.librarian anything by Herbert?` hands the question to the `Librarian`
agent's `agent.librarian.invoke`, with the arguments the model fills in from
the agent's schema. `@function.load-data load data.csv` does the same through
`function.load-data.call`.

The key is the node id the topology graph uses, and the prefix of the
component's own tools (e.g. a `@Task class MetricsFetcher` is addressed as
`@task.metrics-fetcher`). Always writing the namespace keeps a mention
unambiguous as a project grows: a `@Task class Loader` and an
`@Agent class Loader` are `@task.loader` and `@agent.loader`. The chat input
autocompletes the key as you type `@`, matching the name or class name too. A
mention that doesn't match any resolved component's key, such as a bare
`@loader`, is just left as plain text — the turn falls back to the full, unscoped tool
set. A message can only address one component at a time — mentioning
more than one distinct component's key in the same message rejects the
turn with an inline error instead of guessing which one you meant.

## Channels

Besides the assistant, the chat drawer holds the project's outside
conversations: messages people sent by email or a messenger, say, with the
project's replies. A repository takes part by declaring a `conversation()`
([`Conversation`](https://opendataframework.github.io/opendataframework/view/)),
beside its data view, not instead of it:

```python
from opendataframework import Conversation, Repository


@Repository(Message)
class Messages:
    def all(self) -> list[Message]: ...

    def conversation(self) -> Conversation:
        return Conversation(
            channel="support",  # repositories naming the same channel merge
            thread="customer",  # one thread per customer
            time="sent_at",
            text="text",
            direction="direction",  # "in" or "out": which side a message is on
            sender="sender",
        )
```

With any channel, the drawer opens on a list: **Assistant** first, then each
channel with its threads, the one with the latest message first, each showing
its last message. A dot marks a thread with something you haven't seen yet;
which ones you've seen is kept in your browser. A thread shows its messages on
their sides, oldest first. A notification about a record of a repository in a
channel (a message taken in, say) refreshes the list and the open thread.
Channels show even with chat off, read only.

### Cards

A repository in the same channel with no `direction` holds cards instead of
messages: a ticket or a draft reply answering the messages around it. Its
text shows as Markdown when the repository's `content_metadata()` says
`text/markdown`.

```python
@Repository(Ticket)
class Tickets:
    def all(self) -> list[Ticket]: ...

    def conversation(self) -> Conversation:
        return Conversation(channel="support", thread="customer", time="opened", text="body")
```

A card carries its actions: every `@Function` or `@Agent` with an argument
marked as one of the repository's records
([`Record`](https://opendataframework.github.io/opendataframework/repository/)):

```python
from typing import Annotated

from opendataframework import Function, Record


@Function
def close_ticket(
    ticket_id: Annotated[int, Record(Tickets)],  # the ticket's id, its "id" field
    tickets: Tickets,  # injected, as usual
    reply: str | None = None,  # named like Ticket.reply
) -> str: ...
```

Each action is a button on the card. It opens the function's form inside the
card, the same form the inspector shows, with `ticket_id` given already and
hidden. Arguments named like a field of the record (`reply`) start as the
record's value, so a person can change a reply before it goes out. Running it
calls the function as **Call** does, and redraws the card from the record as
it is then. A form being filled in stays open while the thread refreshes
around it.

A record whose thread field is `None` isn't in any thread. The `time` fields of
a channel's repositories have to sort together: a number is read as a Unix
time, a `datetime` as itself and a string as ISO 8601.

The UI checks every conversation when it starts: one naming a field its
entity lacks, or on a repository with no `all()`, fails `Server.start()`.

See [`examples/27-channels`](https://github.com/opendataframework/odf/tree/main/examples/27-channels):
a help desk's messages and tickets in one channel, with a ticket's reply sent
from its card.

### Asking in a thread

With chat on, a thread has the same input as the assistant. What you ask
there is about that thread: the turn is sent with the thread's latest
messages and cards as its context, each card with the tools its actions are
called by and the record it takes. "make it 30, not 20" in a
customer's thread is about that customer's draft, and the model knows which
record to pass. Its tool access is scoped by `@` as anywhere else, by the
full key (`@agent.order-desk`).

The question and the answer show in the thread as notes, set apart from the
messages, since they never reach the other side. The context says so too: only
a card's action does, run when you ask for it.

## History

Conversations with the assistant are kept in `chat.json` (`[project]
chat-file`), next to `layout.json`, so they're reopened after a reload or from
another browser:

- under **Assistant**, **New conversation** starts one, and each kept one is
  listed by its first question, the one changed last first. **Delete** (the
  bin in the header), in an open conversation, removes it;
- each thread holds one conversation of its own, its notes, shown between
  the thread's messages and cards.

Only what was said is kept: a turn's tool calls and their results aren't,
since they're in the logs and **Show run**. A question whose turn failed (the
model ran out of tool calls, or Ollama wasn't there) stays in the
conversation, but isn't sent to the model with the next one, which it would
otherwise answer instead. Each conversation keeps its latest
`[ui] chat-history` turns (default 200). `chat-history = 0` keeps nothing on
the server: each conversation lives in its browser tab, as before, and is
sent whole with each turn.

```toml
[project]
chat-file = "chat.json"

[ui]
chat-history = 200
```

odf doesn't know who is asking yet, so a kept conversation is shared by
everyone using the UI: a thread's notes are the team's notes.

## Full screen

**Expand** (the outward arrows in the drawer's header) shows the chat full
screen in place of the topology, as big as the Notifications view. With
channels or kept conversations, the list stays on the left beside the open
one, the current one marked, so moving between threads takes one click
instead of **Back** (the arrow left of the title). **Collapse** (the same
button, arrows inward) returns to the topology with the drawer still open.
Leaving the view the way any view is left (Esc outside the input, the
Notifications or Activity button, a component picked in the sidebar) does the
same, and **Close** (×) closes the chat. Whether the chat opens full screen
is remembered in your browser.

## Prerequisites

1. Install and run [Ollama](https://ollama.com) locally: `ollama serve`.
2. Pull a tool-calling-capable model: `ollama pull gpt-oss:20b`.
3. Start the project with `chat=True` (and `mcp=True` for tool access).

If the Ollama daemon is unreachable, the chat window shows an inline error
rather than hanging.
