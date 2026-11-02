# Demo

The [examples](examples.md) each show one concept. A demo is a whole
application built with `odf`, closer to a real business, using most of ODF at
once. It lives in
[`demo/`](https://github.com/opendataframework/odf/tree/main/demo) and runs
with `docker compose up`.

## Bakery

[`demo/bakery`](https://github.com/opendataframework/odf/tree/main/demo/bakery)
is a bakery that bakes overnight, delivers to eight restaurants each morning,
and runs its own café. It already uses a café POS, a business messenger,
email and spreadsheets on a shared drive, and none of them talk to each
other. Each tool runs as a simulated service of its own, with its own UI and
API. An `odf` project connects them the ways real integrations do, and
answers the questions that cross them: what to bake tomorrow, which
contracts are losing money, and who to tell when a flour may contain sesame.

```bash
cd demo/bakery
docker compose up --build
```

Then open the bakery's UI at <http://localhost:4747>, the world console
(the demo clock and scenarios) at <http://localhost:8000>, and the tools
next to it. The
[README](https://github.com/opendataframework/odf/tree/main/demo/bakery#readme)
explains why it's built this way, what to try, and the questions to ask
in chat.

### What it shows

| In the bakery | What ODF does | Docs |
|---|---|---|
| The POS and the messenger push webhooks; the mailbox is polled; the sheets are watched; a scheduler runs the bakery's day | Each integration is a `@Service` or `@Component`, and each inbound item one `@Function` call, so it's logged and traced on its own | [Service](https://opendataframework.github.io/opendataframework/service/), [Function](https://opendataframework.github.io/opendataframework/function/) |
| A restaurant's message, a supplier's invoice and a price rise each raise a notice in the UI | Components publish [notifications](https://opendataframework.github.io/opendataframework/notifications/); every open tab shows those with a summary, and the Notifications view keeps them all | [UI](ui.md#run-activity) |
| A message becomes a draft order change, and an invoice runs a chain: prices, then margins, then a renegotiation draft | `@Subscriber`s react in the background, each reaction a call caused by the notification before it, so **Show run** shows the whole chain as one tree | [UI](ui.md#run-activity) |
| The topology shows who reacts to whom before anything happens | Dotted links from each `@Publisher` to the `@Subscriber`s its topics reach | [UI](ui.md#notification-links) |
| Agents draft; people confirm | `@Agent`s with plain rules first and a local model for the rest, writing drafts that `confirm-draft` sends out | [Agent](https://opendataframework.github.io/opendataframework/agent/), [Arguments](ui.md#arguments-invoke-and-call) |
| Messages and invoices as documents, deliveries on a map, prices and café sales over time, margins as a chart | `DocumentView`, `LocationView`, grouped `TimeseriesView`, `chart()` | [Data views](ui.md#data-views) |
| "What do we bake tomorrow?" and "Which restaurants are we losing money on?" | The same agents and functions as MCP tools, and in the chat window on a local model | [MCP](mcp.md), [Chat](chat.md) |

The bakery, the restaurants, the people and the data are all fictional.
