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

> **Work in progress.** So far: the tools, the integrations, the UI showing
> what arrives, and the daily loop: agents drafting order changes and
> specials for a person to confirm, the café's forecast, the bake sheet and
> the delivery run. Agents starting on their own when a message arrives,
> purchasing, margins and allergens come next.

The bakery, the restaurants, the people and the data are all fictional. Phone
numbers are in the 07700 900xxx range set aside for drama, and email domains
are `.example`.

## Start, stop, start over

**Start** the tools and the bakery:

```bash
cd demo/bakery
docker compose up --build
```

The first start seeds the tools with the history of a bakery that's been
trading a while (12 weeks of café orders, two weeks of chats, a month of
email). The bakery's project then onboards: it imports that history through
the tools' APIs.

**Stop** it, keeping everything for next time:

```bash
docker compose down
```

The next `docker compose up` carries on where it stopped: same data, same
time on the demo clock, no seeding or onboarding again.

**Without rebuilding.** `--build` rebuilds the images first, which you only
need the first time and after changing the demo's code. Otherwise:

```bash
docker compose up -d     # start in the background, with the images already built
docker compose stop      # pause: stop the containers, keep them and their data
docker compose start     # carry on after a stop
docker compose logs -f   # follow what the services print
```

**Start over**, with a fresh bakery and new history:

```bash
docker compose down -v
docker compose up --build
```

`-v` also deletes the volumes holding the tools' and the bakery's data, the
mailbox and the shared drive, so the next start seeds and onboards again from
scratch.

**With a local model.** The agents read the usual phrasings with plain
rules, and leave the rest (a freeform party order, say) for a person to
review. To have a model read those, run [Ollama](https://ollama.com) on the
host with a model pulled (`ollama pull llama3.2`), and set
`OLLAMA_URL=http://host.docker.internal:11434` in `.env`.

Settings are in `.env.example`. Copy it to `.env` to change the seed, the
clock's speed or the credentials. New credentials take effect at the next
`docker compose up`. The seed and the speed only apply when you start over,
since the history is already seeded and the clock remembers its speed; the
console changes the speed any time.

## Try it

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
- **Draft the order change.** In the `odf` UI, find the message's id in
  Messages, then invoke the **order-desk** agent with it. A draft appears in
  Drafts: the message, each product before and after, and the reply. Rules
  read the usual phrasings; a freeform message is marked for review unless
  there's a model.
- **Confirm it** by calling **confirm-draft** with the draft's id. The reply
  goes back to the restaurant (watch the messenger's thread, or Mailpit for
  an emailed change), and the change reaches the bake sheet. If tomorrow's
  sheet was already worked out, it's worked out again. **reject-draft** sends
  nothing, and keeps a reason.
- **Watch the day go by.** At 15:00 on the demo clock the café closes: the
  `close-cafe` pipeline counts its leftovers, and the **specials** agent drafts
  tomorrow's specials board from them. At 21:00 the `night-run` pipeline
  forecasts tomorrow's café, works out the bake sheet, and plans the
  delivery run, which `DeliveryRuns` shows on a map. Either runs any time
  with **Execute**.
- **Make it rain** with the console's rainy-week scenario. Nobody forecast
  today's rain, so the café sells less than it baked and leftovers grow;
  tomorrow's forecast knows, and bakes less for the café.
- **Ask from anywhere.** Every agent and function is an MCP tool too, at
  `localhost:4748`, for an assistant of your own to draft and confirm with.
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
| Schedule | `Scheduler` (`@Service`) onboards once, then each day closes the café at 15:00, runs the night run at 21:00 and reconciles the POS at 23:30, on the demo clock | POS |
| Pull | `Weather` (`@Api @Component`) reads the weather forecast that the café's forecast uses | the world, in Open-Meteo's shape |
| Outbound | Confirming a draft sends its reply through `Messenger` or `Mail` (SMTP) | messenger, Mailpit |

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
| `drafts.created` | yes: "Order change for Le Petit awaits confirmation", a warning when it needs review |
| `drafts.confirmed`, `drafts.rejected` | yes |
| `night-run.done` | yes: "Night run for Tue 3 Nov: bake 645 items, 8 deliveries" |

## Agents draft, people confirm

| Agent | Started by | Reads with | Drafts |
|---|---|---|---|
| `order-desk` | a person, on a message (UI, MCP) | rules for the usual phrasings, then the model, else marked for review | an order change and its reply |
| `specials` | `close-cafe` at 15:00, or a person | rules pick the dishes and prices; the model only writes the lines | tomorrow's specials board |

`Model` (`app/model.py`) is a local Ollama, or nothing. An agent asks it only
what its rules can't read, checks what it answers (products that exist, dates
in range, sensible quantities), and marks anything it isn't sure of for review
rather than guessing. Nothing an agent drafts reaches a restaurant or the
bake sheet until a person calls `confirm-draft`.

The numbers a person checks a draft against are plain arithmetic, in
`app/planning.py`: `forecast` (the weekday's average over six weeks, times the
weather and bank holidays), `bake_sheet` (the restaurants' standing orders
with every confirmed change, plus the café's forecast and a tenth more),
`plan_deliveries` (earliest kitchen first) and `count_leftovers`.

## Structure

```
bakery/
├── compose.yaml          # the tools, Mailpit, and the bakery, ports on loopback only
├── .env.example          # seed, clock speed, credentials
├── Dockerfile            # the bakery: odf from this repository's source, plus app/
├── config.toml           # the bakery's odf config: the tools' addresses, ports, intervals
├── app/                  # the bakery's odf project
│   ├── clients.py        # Clock, Pos, Messenger, Drive, Weather, Mail: one per tool
│   ├── ingest.py         # ingest_message, ingest_sale, import_sheets
│   ├── services.py       # WebhookReceiver, Mailbox, SharedDrive, Scheduler
│   ├── tasks.py          # history imports, POS reconciliation
│   ├── pipelines.py      # Onboard, NightRun, CloseCafe
│   ├── agents.py         # order-desk, specials
│   ├── drafts.py         # confirm_draft, reject_draft
│   ├── rules.py          # what the agents read without a model
│   ├── model.py          # Model: a local Ollama, or nothing
│   ├── planning.py       # forecast, bake_sheet, plan_deliveries, count_leftovers
│   ├── repositories.py   # Products, Restaurants (map), Messages, Drafts, DeliveryRuns (map), ...
│   ├── entities.py
│   ├── storages.py       # one SQLite database
│   └── settings.py       # environment over config.toml
└── tools/                # the simulated tools, one small web app each
    ├── world.py          # demo clock, actors, weather, history, scenarios, console
    ├── pos.py            # till, REST API, signed webhooks with retries
    ├── messenger.py      # chats, signed webhooks, send and history APIs
    ├── common.py, data.py
    └── Dockerfile
```

Its tests are in `tests/demo/bakery/` and need neither Docker nor the
network: `poetry run pytest tests/demo`.
