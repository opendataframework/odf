# 27 — Channels

A help desk's conversations with its customers in the chat drawer, beside the
assistant, with the ticket answering them as a card to act on.

`app/repositories.py` holds two repositories in one channel, `support`:

- `Messages` declares a `conversation()` naming, by role, its `thread`
  (`customer`), `time`, `text`, `direction` and `sender` fields: its records
  are messages, one thread per customer, on the side they were sent from.
- `Tickets` declares one in the same channel with no `direction`: its
  records are cards, each in its customer's thread. Its `content_metadata()`
  says `text/markdown`, so a card's body renders as Markdown.

`app/functions.py` has the card's one action. `send_reply` takes the ticket
as `ticket_id: Annotated[int, Record(Tickets)]`, so it's offered on each
ticket's card with the ticket's id given. Its `reply` argument is named like
`Ticket.reply`, so the form starts with the ticket's reply, to change before
it's sent. Sending saves the reply in `Messages`, going out, and publishes a
notification about the ticket, which refreshes the thread in every open UI.

`odf` shows the channel in three places:

- **UI**: **Chat** in the header opens on the list of threads, the one with
  the latest message first: **Bob**, then **Ada**. Ada's thread has her
  message and the ticket as a card. **Send reply** opens the form with the
  reply filled in.
- **MCP**: `list_channels` and `read_thread` read them. A card's actions are
  listed with the tool each is run by, here `function.send-reply.call`, and
  the record's argument to pass.
- **Chat**: with a model, asking in Ada's thread is about her thread: the
  turn is sent with its messages and cards, and the answer stays in the
  thread as notes.

## Structure

```
27-channels/
├── README.md
├── config.toml
├── main.py               # entry point: reads the channel over MCP and sends a reply
└── app/
    ├── __init__.py       # imports all modules so decorators register at startup
    ├── entities.py       # Message, Ticket — @Entity
    ├── repositories.py   # Messages, Tickets — @Storage @Repository, each with a conversation()
    └── functions.py      # send_reply — @Function, the ticket card's action
```

## Dependencies

Needs the `mcp` extra (`pip install "odf[mcp]"`) for the MCP server and its
client. It is already in the repo's `dev` dependency group, so a plain
`poetry install` covers it.

## Run it

```bash
cd examples/27-channels
python main.py
```

Expected output:

```
Topology UI running at http://127.0.0.1:4747
MCP server running at http://127.0.0.1:4748/mcp

Channel 'support', threads: ['Bob', 'Ada']
  [in] My order #1042 hasn't arrived, it's been a week.
  [card] ### Late order #1042

The card's action: function.send-reply.call(ticket_id=1)
  filled in from the ticket: {"reply": "So sorry, Ada: the courier lost it. A new one goes out by express today."}
  sent: So sorry, Ada! A new one goes out by express today, on us.

Ada's thread now ends: [out] So sorry, Ada! A new one goes out by express today, on us.
```

Or start it with the CLI and send the reply from the chat drawer, with chat
on if a model is running:

```bash
odf run --mcp --chat
```
