# Bakery

A bakery bakes overnight, delivers bread to eight restaurants each morning,
and runs its own café with a breakfast menu. Like most small businesses, it
already runs on good tools, and none of them talk to each other:

- **a café POS**, where every coffee and croissant is rung up;
- **a business messenger**, where restaurants send order changes, often late
  in the evening;
- **email**, for the restaurants that prefer it and for suppliers;
- **spreadsheets on a shared drive**: products and prices, the restaurants,
  their standing orders, and this quarter's contract prices.

This demo doesn't replace any of them. It connects them with an `odf`
project, the way a developer would for a real bakery: through the tools' own
APIs and webhooks, a mailbox, and the shared drive. The result is one place
where the bakery's people, and later its agents, can see and work with
everything at once.

> **Work in progress.** This is phase 3 of the plan: the tools, the
> integrations, and the UI showing what arrives. Drafts, the bake sheet,
> deliveries, margins and allergens come next.

The bakery, the restaurants, the people and the data are all fictional. Phone
numbers are in the 07700 900xxx range set aside for drama, and email domains
are `.example`.

## Run it

```bash
cd demo/bakery
docker compose up --build
```

The first start seeds the tools with the history of a bakery that's been
trading a while (12 weeks of café orders, two weeks of chats, a month of
email). The bakery's project then onboards: it imports that history through
the tools' APIs.

| Open | For |
|---|---|
| http://localhost:4747 | The bakery's `odf` UI |
| http://localhost:8000 | The world console: the demo clock and scenarios |
| http://localhost:8001 | The café POS's till |
| http://localhost:8002 | The messenger, where you can write as a restaurant |
| http://localhost:8025 | The bakery's mailbox (Mailpit) |

Things to try:

- **Write as a restaurant.** In the messenger, pick a restaurant and send
  "2 extra baguettes tomorrow please". A notice appears in the `odf` UI within
  a second or two. **Open** goes to the Messages, and **Show logs** shows the
  call that took the message in.
- **Ring up a sale** at the POS's till. It arrives in `CafeSales` by webhook,
  with no notice (a sale every few minutes isn't news), but the topology shows
  the call.
- **Run a scenario** from the world console: a party order, an emailed order
  change, a café rush, or a missed webhook. The nightly reconciliation (at
  23:30 on the demo clock) finds the sale whose webhook never came.
- **Edit a sheet** on the shared drive. Copy one out with `docker compose cp
  bakery:/shared-drive/restaurants.csv .`, change it, and copy it back with
  `docker compose cp restaurants.csv bakery:/shared-drive/`. The bakery
  imports the sheets again and says so.
- **Speed the clock up** in the console. At the default 60×, a day takes 24
  minutes. Restaurants write in the evening, from 17:00.

Settings are in `.env.example`. Copy it to `.env` to change the seed, the
clock's speed or the credentials. `docker compose down -v` starts over.

## How it fits together

```
 world ── café customers ──▶ POS ───── order.created webhook ──▶┐
   │                          ▲                                   │
   │                          └── nightly reconciliation (API) ◀──┤
   ├─ restaurants ──▶ messenger ── message webhook ──────────────▶│  bakery (odf)
   ├─ restaurants, suppliers ──▶ Mailpit ◀── POP3, every 5 s ─────┤
   └─ writes the sheets ──▶ shared drive ◀── watched ─────────────┘
```

Each kind of integration is one `odf` component:

| How | Component | From |
|---|---|---|
| Push | `WebhookReceiver` (`@Api @Service`) checks each webhook's signature and hands each order or message on | POS, messenger |
| Poll | `Mailbox` (`@Messaging @Service`) reads new mail over POP3, leaving it on the server | Mailpit |
| Files | `SharedDrive` (`@Service`) re-imports the sheets when one changes | the shared drive |
| Schedule | `Scheduler` (`@Service`) onboards once, and reconciles the POS each night on the demo clock | POS |

Whatever brings an item in, the item goes through one function in
`app/ingest.py` (`ingest_message`, `ingest_sale`, `import_sheets`). That
function saves it, takes it only once (a webhook retried does no harm), and
publishes a notification. Each item is a call of its own, so it's logged, it
shows on the topology, and its notice's **Show logs** finds it.

| Notification | Notice in the UI |
|---|---|
| `messages.received` | yes: "Le Petit: 2 extra baguettes tomorrow please" |
| `pos.sale` | no: for components only |
| `sheets.changed` | yes |
| `pos.reconciled` | yes, a warning |
| `bakery.onboarded` | yes, once |

## Structure

```
bakery/
├── compose.yaml          # the tools, Mailpit, and the bakery, ports on loopback only
├── .env.example          # seed, clock speed, credentials
├── Dockerfile            # the bakery: odf from this repository's source, plus app/
├── config.toml           # the bakery's odf config: the tools' addresses, ports, intervals
├── app/                  # the bakery's odf project
│   ├── clients.py        # Clock, Pos, Messenger, Drive: one per tool
│   ├── ingest.py         # ingest_message, ingest_sale, import_sheets
│   ├── services.py       # WebhookReceiver, Mailbox, SharedDrive, Scheduler
│   ├── tasks.py          # history imports, POS reconciliation
│   ├── pipelines.py      # Onboard
│   ├── repositories.py   # Products, Restaurants (map), Messages, CafeSales (chart), ...
│   ├── entities.py
│   ├── storages.py       # one SQLite database
│   └── settings.py       # environment over config.toml
└── tools/                # the simulated tools, one small web app each
    ├── world.py          # demo clock, actors, history, scenarios, console
    ├── pos.py            # till, REST API, signed webhooks with retries
    ├── messenger.py      # chats, signed webhooks, send and history APIs
    ├── common.py, data.py
    └── Dockerfile
```

Its tests are in `tests/demo/bakery/` and need neither Docker nor the
network: `poetry run pytest tests/demo`.
