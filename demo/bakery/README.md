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
where the bakery's people and its agents see and work with everything at
once.

## Why

A small business doesn't lack software. The bakery's POS knows every sale,
the messenger every order change, the inbox every invoice, and the sheets
every recipe and contract. Each tool is good at its job, and each is an
island: nobody joined them up, because nobody at a bakery has the time.

More and more of these tools come with an assistant of their own. The POS's
can say what sold best last Tuesday, and the inbox's can summarise an
invoice. Each sees only its own tool's data, so each answers only its own
tool's questions.

The questions that matter to the bakery cross the tools. What to bake
tomorrow takes the standing orders from a sheet, last night's changes from
the messenger and email, and the café's sales from the POS. Which
restaurants it's losing money on takes the suppliers' invoices from the
inbox, and the recipes and contract prices from the sheets. Who to tell when
the mill sends a flour that may contain sesame takes the invoice, the
recipes, and who orders what. No one tool's assistant can answer any of
them.

`odf` doesn't replace any of the tools. It connects them the ways real
integrations do: webhooks the POS and the messenger push, a mailbox it
polls, a schedule on the bakery's day, a shared drive it watches, and
replies it sends back out by messenger and email. Everything lands in one
model of the business, which people see in the UI and agents work from. The
agents draft, and people decide: an order change, a price renegotiation and
an allergen notice each wait for someone to confirm them, and nothing
leaves the bakery until someone does.

It runs on the bakery's own machine, with a local model through Ollama, or
with no model at all: plain rules read the usual phrasings, and whatever
they can't read waits for a person.

And it grows as the business does. Webhooks can go through a durable broker,
so nothing is lost across a restart; an accounting tool can join the
others; and each new source is one more integration feeding the same model.

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
rm -f chat.json annotations.json
docker compose up --build
```

`-v` also deletes the volumes holding the tools' and the bakery's data
(its logs and its notification history among them), the mailbox and the
shared drive, so the next start seeds and onboards again from scratch. The
chat's conversations and the labels are files in this directory instead (see
"What outlasts a restart" below), so they're removed by hand, or their
threads' notes would point at drafts the new bakery doesn't have.

**With a local model.** The agents read the usual phrasings with plain
rules, and leave the rest (a freeform party order, say) for a person to
review. To have a model read those, run [Ollama](https://ollama.com) on the
host with a model pulled (`ollama pull gpt-oss:20b`, which the prompts are
tuned on), and set `OLLAMA_URL=http://host.docker.internal:11434` in `.env`.
The UI's chat window uses the same Ollama (`[project.chat]` in
`config.toml`); without one, it says it can't reach it, and everything else
works as before.

Settings are in `.env.example`. Copy it to `.env` to change the seed, the
clock's speed or the credentials. New credentials take effect at the next
`docker compose up`. The seed and the speed only apply when you start over,
since the history is already seeded and the clock remembers its speed; the
console changes the speed any time.

**Unreleased opendataframework.** The image installs `odf` from this
repository and resolves `opendataframework` from PyPI. When `odf` here needs
an `opendataframework` version that isn't on PyPI yet, serve its wheel from
a local package index and point the build at it with `ODF_INDEX_URL`, which
pip looks in besides PyPI:

```bash
# in opendataframework/
poetry build
mkdir -p /tmp/wheels && cp dist/*.whl /tmp/wheels/

docker run -d --rm -p 8080:8080 -v /tmp/wheels:/data/packages \
  pypiserver/pypiserver:latest run -a . -P .

cd demo/bakery
ODF_INDEX_URL=http://host.docker.internal:8080/simple/ docker compose up --build
```

## Try it

| Open | For |
|---|---|
| http://localhost:4747 | The bakery's `odf` UI |
| http://localhost:8000 | The world console: the demo clock, scenarios and tours |
| http://localhost:8001 | The café POS's till |
| http://localhost:8002 | The messenger, where you can write as a restaurant |
| http://localhost:8025 | The bakery's mailbox (Mailpit) |

Things to try:

- **Take a tour** from the world console. Each one plays a whole flow: a
  restaurant's message becoming a draft you confirm, the butter spike through
  margins to new prices, or the sesame substitution through labels to a notice
  for every restaurant. A tour starts the flow, says at each step what to look
  at and where, and moves on when the bakery's notifications say it got there.
  At the end, confirm the draft from its card, or let **Do it for me** confirm
  it. The clock stops while a tour plays, so nothing else interrupts it. The
  bullets below are the same flows, and more, by hand.
- **Write as a restaurant.** In the messenger, pick a restaurant and send
  "2 extra baguettes tomorrow please". A notice appears in the `odf` UI within
  a second or two. **Open** goes to the Messages, and **Show logs** shows the
  call that took the message in.
- **Watch it become a draft.** Right after, a second notice says the order
  change awaits confirmation: `Drafting` reacted to the message and had the
  **order-desk** agent draft it, on a worker of its own, so the messenger's
  webhook never waited. Open **Chat** in the header: under **restaurants**,
  the restaurant's thread has its message, and the draft answering it as a
  card: the message, each product before and after, and the reply. Rules read
  the usual phrasings; a freeform message is marked for review unless there's
  a model. A message from anyone not on the restaurants sheet gets no draft
  by itself, and no thread; invoke **order-desk** with its id in Messages to
  draft one anyway. Every draft is in Drafts too, a document each.
- **Follow it through.** **Show run** on either notice opens the whole run as
  one tree: the message taken in, its notification, `Drafting`'s reaction
  under it, the order-desk's draft, and the notification that the draft
  awaits confirmation. On the topology, the dotted link from
  `ingest-message` to `Drafting` lights up while it reacts.
- **Confirm it** from the card: **Confirm draft** opens with the reply and the
  changes filled in, to change before it goes. The reply goes back to the
  restaurant (watch the messenger's thread, or Mailpit for an emailed change),
  shows in the bakery's thread on its side, and the change reaches the bake
  sheet. If tomorrow's sheet was already worked out, it's worked out again.
  **Edit draft** saves a change without sending it, and **Reject draft** sends
  nothing and keeps a reason. **confirm-draft**, **edit-draft** and
  **reject-draft** take the draft's id anywhere else (the inspector, MCP).
- **Write again before confirming.** Send "2 extra croissants tomorrow please"
  from the same restaurant while its draft waits: the card turns outdated,
  and a new one answers both messages, so the two can't both be sent. If you
  had edited the old one, the new one says what you'd changed.
- **Ask in the thread.** With a model, type "@agent.order-desk make it 30
  croissants" in the restaurant's thread: the agent drafts again with your
  instruction, from the message the thread shows it, and the old card turns
  outdated. The question and its answer stay in the thread as notes, which
  the restaurant never sees.
- **Watch the day go by.** At 15:00 on the demo clock the café closes: the
  `close-cafe` pipeline counts its leftovers, and the **specials** agent drafts
  tomorrow's specials board from them. At 21:00 the `night-run` pipeline
  forecasts tomorrow's café, works out the bake sheet, and plans the
  delivery run, which `DeliveryRuns` shows on a map. Either runs any time
  with **Execute**.
- **Spike the price of butter** with the console's butter-spike scenario.
  Vale Dairy's invoice arrives in Mailpit with a PDF attached, and a notice
  says so. The **invoice-clerk** reads the PDF, records each ingredient's
  price in `IngredientPrices`, and a warning names the rise. `Costing` works
  out what each restaurant's contract leaves at the new price, and a second
  warning names the two that no longer cover their cost. For each of those
  restaurants, the **account-manager** drafts an email asking for new
  prices: cost plus 15%, from the Monday after next. Confirming it emails
  the restaurant (watch Mailpit). `Costing`'s **Chart** shows the weekly
  margin by restaurant; **what-if** answers "what if butter cost £12?"
  without an invoice, and **margins** lists every contract's margin.
- **Get the farm's egg note** with the farm-invoice scenario. Hill Farm's
  invoice is a few handwritten-looking lines, which the rules can't read: a
  model reads it into a draft to confirm, and with no model, it waits for a
  person. Open it in `Invoices` to see the PDF.
- **Swap the flour** with the sesame-substitution scenario. Millers Ltd's
  invoice says, under the flour, that this week's comes from another mill
  and may contain sesame. The invoice-clerk records the prices as usual, and
  a warning says the flour now may contain sesame. `Labelling` records that
  at once (every label then says so), and a second warning names the seven
  labels it changed and the restaurants taking those products. The
  **allergen-officer** drafts one notice per restaurant, naming its own
  products and their labels, with the label changes for the café. Confirming
  emails every notice (watch Mailpit). **labels** gives every product's
  label, and **trace-ingredient** follows an ingredient to the products it
  goes into and the restaurants taking them.
- **Make it rain** with the console's rainy-week scenario. Nobody forecast
  today's rain, so the café sells less than it baked and leftovers grow;
  tomorrow's forecast knows, and bakes less for the café.
- **Look back** with the bell in the header: every notice so far, newest
  first, filtered by topic, publisher or level, with the same **Open**,
  **Show logs** and **Show run**.
- **Ask from anywhere.** Every agent and function is an MCP tool too, at
  `localhost:4748`, for an assistant of your own to draft and confirm with.
- **Ring up a sale** at the POS's till. It arrives in `CafeSales` by webhook,
  with no notice (a sale every few minutes isn't news), but the topology shows
  the call.
- **Run a scenario** from the world console: a party order, an emailed order
  change, a café rush, or a missed webhook. Suppliers also email their weekly
  invoices on their own, at 09:00 on their day. The nightly reconciliation (at
  23:30 on the demo clock) finds the sale whose webhook never came.
- **Edit a sheet** on the shared drive. Copy one out with `docker compose cp
  bakery:/shared-drive/restaurants.csv .`, change it, and copy it back with
  `docker compose cp restaurants.csv bakery:/shared-drive/`. The bakery
  imports the sheets again and says so.
- **Speed the clock up** in the console. At the default 60×, a day takes 24
  minutes. Restaurants write in the evening, from 17:00.

## Ask it

The UI's chat window (**Chat** in the header) and an MCP client of
your own (`localhost:4748/mcp`) see the same tools: every agent, every
function, and every repository's records. With the chat's model running,
ask:

- **"What do we bake tomorrow?"** It works out tomorrow's bake sheet
  (`bake-sheet`): the restaurants' orders with every confirmed change, and
  the café's forecast.
- **"Which restaurants are we losing money on?"** It reads the margins
  (`margins`): every contract's margin at today's prices, those below cost
  first.
- **"What if butter went up to £12 a kilo?"** `what-if`, without an invoice.
- **"Who do we have to tell if the flour has sesame in it?"** It follows the
  flour (`trace-ingredient`) to the products it goes into and the
  restaurants taking them.
- **"What's waiting for me?"** The drafts still pending, from `Drafts`.

Mention a component with `@` to hand it the question: `@agent.order-desk
draft message 12`, or `@repository.invoices which came from Hill Farm?`.
The model then sees only that component's tools, so it answers sooner and
picks the right one: `@repository.drafts what's waiting for me?`. Answers
vary from run to run with a local model; asking again, or more narrowly,
usually settles it. Confirming a draft by asking works too, but a draft is
there to be read first: its card, in the restaurant's thread, is the place.

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
| Push | `WebhookReceiver` (`@Service`) checks each webhook's signature and hands each order or message on | POS, messenger |
| Poll | `Mailbox` (`@Service`) reads new mail over POP3, leaving it on the server; an email with a PDF attached is a supplier's invoice | Mailpit |
| Files | `SharedDrive` (`@Service`) re-imports the sheets when one changes: products, restaurants, standing orders, contracts, ingredients, recipes and allergens | the shared drive |
| Schedule | `Scheduler` (`@Service`) onboards once, then each day closes the café at 15:00, runs the night run at 21:00 and reconciles the POS at 23:30, on the demo clock | POS |
| Pull | `Weather` (`@Component`) reads the weather forecast that the café's forecast uses | the world, in Open-Meteo's shape |
| Outbound | Confirming a draft sends its reply through `Messenger` or `Mail` (SMTP), and new prices by `Mail` | messenger, Mailpit |

Whatever brings an item in, the item goes through one function in
`app/ingest.py` (`ingest_message`, `ingest_sale`, `ingest_invoice`,
`sync_sheets`). That
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
| `drafts.confirmed`, `drafts.rejected`, `drafts.edited` | yes |
| `drafts.outdated` | yes: "Order change for Le Petit drafted again", when a newer message or an instruction replaced a draft |
| `invoices.received` | yes: "Vale Dairy: Invoice VAL-2026-0005" |
| `prices.changed` | only when a price moved 5% or more, a warning from a 10% rise: "Vale Dairy: butter up 55% (£7.20 to £11.15 a kg)" |
| `margins.below-cost` | yes, a warning: "2 contracts now below cost: The Fig Tree's brioche, Olive & Ash's croissant" |
| `ingredients.changed` | yes, a warning: "Millers Ltd: strong white flour now may contain sesame" |
| `allergens.changed` | yes, a warning: "7 labels now may contain sesame: baguette, brioche, ... 8 restaurants to tell" |
| `night-run.done` | yes: "Night run for Tue 3 Nov: bake 645 items, 8 deliveries" |

A notice shows once, as it arrives. The bell in the UI's header opens
**Notifications**: every notice so far, newest first, from every component,
with the notice's own **Open**, **Show logs** and **Show run**. Filter it by
topic (`drafts.*` for every draft), publisher or level; **All topics** adds
the ones for components only, such as each café sale. The MCP tool
`recent_notifications` reads the same, so chat can answer "what happened
overnight?". It keeps each notice's summary, not its payload, and a café
sale is a notification too, so `config.toml` gives the history room of its
own (`history-max-bytes`) for days of notices.

## Agents draft, people confirm

| Agent | Started by | Reads with | Drafts |
|---|---|---|---|
| `order-desk` | `Drafting`, when a restaurant's message arrives; or a person, on any message (UI, MCP), or with an instruction from the restaurant's thread | rules for the usual phrasings, then the model, else marked for review | an order change and its reply, for the message and those the restaurant's open draft already answered |
| `specials` | `close-cafe` at 15:00, or a person | rules pick the dishes and prices; the model only writes the lines | tomorrow's specials board |
| `invoice-clerk` | `Purchasing`, when an invoice arrives; or a person, on any invoice | rules for the typed invoices, then the model, else marked for review | nothing when the rules read it cleanly: it records the prices; otherwise its reading, to confirm |
| `account-manager` | `Renegotiating`, when a contract falls below cost; or a person | rules work out the prices; the model only writes the email | an email to the restaurant asking for new prices |
| `allergen-officer` | `AllergenNotices`, when a label changes; or a person, on an ingredient | rules only: an allergen notice's wording has to be exact | a notice for each restaurant taking what changed, and the café's label changes |

`Drafting` (`app/reactions.py`) is a `@Subscriber` of `messages.received`,
delivered in the background: the `odf` runtime subscribes it while it runs,
and hands it each message on a worker thread of its own, so a slow model
never holds up the webhook or the mailbox. Each reaction is a call of its
own whose cause is the message's notification, so the logs and the trace
lead from the message to its draft. History caught up on (the first
mailbox check, onboarding) is saved without a notification, so old messages
don't all become drafts at once.

The same runs for invoices, a chain of three reactions in
`app/reactions.py`, each a call caused by the notification before it:
`Purchasing` has the invoice-clerk read each invoice as it arrives; once its
prices are recorded, `Costing` works out the margins again and names any
contract that newly falls below cost; and `Renegotiating` has the
account-manager draft new prices for each restaurant it names. An invoice
is a fact, not a decision, so a clean reading is recorded without a draft:
nothing goes out, and nobody is committed to anything. A model's reading,
and everything that leaves the bakery, waits for a person.

An allergen a supplier declares runs a chain of its own: the invoice-clerk
announces it (`ingredients.changed`), `Labelling` records it and names the
labels it changes (`allergens.changed`), and `AllergenNotices` has the
allergen-officer draft the notices. Recording the allergen doesn't wait for
anyone: it errs on the safe side. Telling the restaurants does.

The topology is laid out by area (`layout.json`): the integrations on the
left, from each tool's client through its service to the function that
takes its items in; then one band each for wholesale, the café, production,
purchasing and margins, and allergens, read left to right from the data to
the agent and the reaction; and the drafts on the right, where every agent's
work ends up. Each band is also a `Layer` (`app/layers.py`), so the
sidebar groups the nodes the same way, and each area has its own color.
Only `SQLite`, the database every area shares, stays in the built-in
`Storage`. The nodes standing for something in the bakery have an icon to
match: the bakery draws its own in `icons/bakery.js` (an oven, a bread
rack, an invoice, the messenger, flour sacks...), loaded through
`[ui] icon-scripts`, and uses odf's built-in ones where they fit (the till,
the delivery truck, the mailbox). Services, agents, reactions and the
other functions keep their type's icon. Each node's icon is saved in
`layout.json`, beside its place. The UI wears odf's built-in `ink` theme
(`[ui] theme` in `config.toml`).

That's the whole system, and most of it isn't what a manager looks at. The
UI opens on the **Bakery** view (`[ui.views.manager]` in `config.toml`):
the bakery's data, the agents drafting from it, the night run and closing
the café, what a person does to a draft (confirm, edit, reject), and the
questions a manager asks themselves: the margins, what a price change would
do, where an ingredient ends up, what each label must say. A routine's
steps (the forecast, the bake sheet, the delivery plan, counting the
leftovers) stay hidden behind it, and so does the wiring: the tools'
clients, the services taking their items in, the imports, the model and
the clock. The switcher in the header turns to the **System** view, which
shows all of it. Each view keeps its own places in `layout.json` (the
manager's under `_views`), so moving a node in one leaves the other as it
was. A view only changes what's drawn: the chat and MCP reach everything
from either. Moving a node or picking another icon in
the UI saves it in the container, so it holds until the container is
recreated (`docker compose down`).

The topology draws each of these chains before anything happens: a dotted
link runs from each publisher to each reaction its topics reach, from
`ingest-message` to `Drafting`, from `ingest-invoice` to `Purchasing`, from
the invoice-clerk to `Costing` and `Labelling`, and on down each chain. A
link lights up while its reaction runs, and **Show run** on any notice in a
chain opens the whole of it, from the email that started it.

`Model` (`app/model.py`) is a local Ollama, or nothing. An agent asks it only
what its rules can't read, checks what it answers (products that exist, dates
in range, sensible quantities), and marks anything it isn't sure of for review
rather than guessing. Nothing an agent drafts reaches a restaurant or the
bake sheet until a person calls `confirm-draft`.

The numbers a person checks a draft against are plain arithmetic, in
`app/planning.py`: `forecast` (the weekday's average over six weeks, times the
weather and bank holidays), `bake_sheet` (the restaurants' standing orders
with every confirmed change, plus the café's forecast and a tenth more),
`plan_deliveries` (earliest kitchen first) and `count_leftovers`; and, in
`app/margins.py`, each product's unit cost (its recipe at the latest invoiced
prices, bake time included), `margins` and `what_if`; and, in
`app/allergens.py`, each product's label from its recipe (`labels`), and
`trace_ingredient`.

## Design notes

Choices that aren't obvious from the code:

- **No file-format libraries.** The sheets are CSV, not `.xlsx`, and the
  suppliers' invoices are real PDFs that `tools/invoices.py` writes and
  `app/pdf.py` reads by hand. Each image stays small, and an invoice still
  arrives the way a real one does: as an attachment to read.
- **One call per inbound item.** Every webhook, email and sheet goes through
  a function in `app/ingest.py`, so each item gets its own call: logged,
  traced, and found by its notice's **Show logs** and **Show run**. A run
  starts at that function, not at the webhook: an HTTP handler isn't a call
  the framework makes, and the climb never goes into a service's `run()`,
  which lasts as long as the service does.
- **Catching up is quiet.** History imported at onboarding, and mail found on
  the mailbox's first check, is saved without a notification, so old
  messages don't all become drafts at once.
- **Reactions run in the background.** Every subscriber in
  `app/reactions.py` is delivered on a worker of its own, so a slow model
  never holds up a webhook or the mailbox. It also keeps a chain in order:
  `Costing`'s below-cost warning follows the price notice that caused it,
  instead of arriving inside it.
- **Rules first, then the model, then a person.** An agent reads what its
  rules can, asks the model only for the rest, and checks the answer
  (products that exist, dates in range, sensible quantities). Anything it
  isn't sure of is marked for review. The allergen-officer uses no model at
  all, since a notice's wording has to be exact.
- **A fact isn't a decision.** An invoice the rules read cleanly is recorded
  at once, and so is an allergen a supplier declares, which errs on the safe
  side. What goes out of the bakery (a reply, new prices, a notice) waits for
  a person. `confirm-draft` sends first and saves after, so a reply that
  fails leaves the draft pending.
- **One thread per restaurant.** Messenger and email go in the same thread,
  since a restaurant is one customer whichever it writes with, and each
  message is tagged with how it came. What the bakery sends is saved in
  Messages too, going out, so a thread has both sides.
- **A newer message outdates a draft.** A restaurant that writes again before
  its draft is confirmed gets one new draft, reading the new message with
  those the old draft answered, and the old one can't be confirmed any more.
  Two drafts answering the same restaurant could otherwise both be sent. A
  message nobody drafted for, such as history caught up on at onboarding,
  isn't folded in, so a draft never answers last month's requests.
- **What's sent is what the record shows.** An edit is saved on the draft
  (its author becomes "edited") before anything goes out, so the draft shows
  what was sent, not what was drafted. A draft replaced after an edit says,
  in the new one, what the person had changed, rather than dropping it.
- **Safe to call by mistake.** A model in chat may call a tool nobody asked
  for. `sync-sheets` leaves alone the records of a sheet that isn't on the
  drive, so it can't empty a table.
- **The bakery's own mail is skipped.** Mailpit's mailbox also holds what
  the bakery sends, so the mailbox ignores the bakery's address.
- **What outlasts a restart.** The demo clock is saved every second, so a
  stopped stack carries on where it was. The bakery's logs, and with them
  its notification history, live on its data volume; `docker compose down -v`
  starts them over. Compose mounts `demo/bakery/` itself as the project
  directory, so what the UI saves next to `config.toml` lands there on the
  host and outlasts a rebuild: a layout you arrange (`layout.json`, which is
  committed, so moving a node shows up in `git diff`), the chat's
  conversations (`chat.json`) and labels (`annotations.json`), both ignored
  by git. The container writes as uid 1000, which a Linux host's own user
  usually is.

## Structure

```
bakery/
├── compose.yaml          # the tools, Mailpit, and the bakery (this directory mounted), ports on loopback only
├── .env.example          # seed, clock speed, credentials
├── Dockerfile            # the bakery: odf from this repository's source, plus app/
├── config.toml           # the bakery's odf config: the tools' addresses, ports, intervals, the UI's views
├── layout.json           # the topology's layout: the integrations, then one band per area, each node's icon, and the manager view's own places
├── icons/bakery.js       # the bakery's own topology icons: oven, bread rack, invoice, messenger, ...
├── app/                  # the bakery's odf project
│   ├── layers.py         # one Layer per area: integrations, wholesale, cafe, production, ...
│   ├── clients.py        # Clock, Pos, Messenger, Drive, Weather, Mail: one per tool
│   ├── ingest.py         # ingest_message, ingest_sale, ingest_invoice, sync_sheets
│   ├── services.py       # WebhookReceiver, Mailbox, SharedDrive, Scheduler
│   ├── tasks.py          # history imports, POS reconciliation
│   ├── pipelines.py      # Onboard, NightRun, CloseCafe
│   ├── agents.py         # order-desk, specials
│   ├── reactions.py      # Drafting, Purchasing, Costing, Renegotiating, Labelling, AllergenNotices
│   ├── allergens.py      # labels, trace_ingredient, allergen-officer
│   ├── purchasing.py     # invoice-clerk, and the rules for reading an invoice
│   ├── margins.py        # unit costs, margins, what_if, the margin chart, account-manager
│   ├── pdf.py            # reading a PDF's text, with no PDF library
│   ├── drafts.py         # confirm_draft, reject_draft
│   ├── rules.py          # what the agents read without a model
│   ├── model.py          # Model: a local Ollama, or nothing
│   ├── planning.py       # forecast, bake_sheet, plan_deliveries, count_leftovers
│   ├── repositories.py   # Products, Restaurants (map), Messages, Drafts, Invoices (PDFs), IngredientPrices (chart), ...
│   ├── entities.py
│   ├── storages.py       # one SQLite database
│   └── settings.py       # environment over config.toml
└── tools/                # the simulated tools, one small web app each
    ├── world.py          # demo clock, actors, weather, history, scenarios, console
    ├── pos.py            # till, REST API, signed webhooks with retries
    ├── messenger.py      # chats, signed webhooks, send and history APIs
    ├── invoices.py       # the suppliers' invoices, as PDFs, with a tiny PDF writer
    ├── common.py, data.py
    └── Dockerfile
```

Its tests are in `tests/demo/bakery/` and need neither Docker nor the
network: `poetry run pytest tests/demo`.
