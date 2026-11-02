# 26 — Notifications

A café counter that publishes what happens as
[notifications](https://opendataframework.github.io/opendataframework/notifications/),
and the UI showing them. The `Counter` service takes an order every few
seconds. Each order goes through the `take_order` function, which saves it and
publishes:

| Topic | Level | Summary | Shown in the UI |
|---|---|---|---|
| `orders.received` | `info` | `Table 4: flat white` | yes, closes by itself |
| `pantry.low` | `warning` | `Oat milk running low: 1 left` | yes, stays until closed |
| `pantry.out` | `error` | `Out of oat milk: table 6's oat flat white not taken` | yes, stays and looks like a failure |
| `kitchen.ticket` | `info` | none | no: it's for the `Kitchen` component |

**Execute** on `Restock` puts the pantry back and publishes
`pantry.restocked` as a `success`. Oat milk starts short, so the warning and
the error come up within the first minute.

Every open tab of the UI shows each notification that has a summary as a
notice in the top-right corner, adds it to the activity log, and briefly rings
the publisher's node. Open a second tab and both show the same notices,
whoever caused them.

- **Open** goes to the repository the notification is about: `Orders` for a
  new order, `Pantry` for the stock ones. That's the notification's
  `subject`.
- **Show logs** opens `take_order`'s logs and highlights the call that
  published it, because the notification records that call as its `parent`.
- **Show run** opens the order's whole run: `take_order`, the notifications
  it published, and under `kitchen.ticket` the `Kitchen`'s
  `on_notification()`. It starts at `take_order`, not at `Counter`'s
  `run()`, which lasts as long as the service does.

## Events and notifications

The UI shows two things as they happen, from two separate streams:

- **Events** are the framework's record of every call it makes: `Counter`
  calling `take_order`, **Execute** running `Restock`. They drive the rings
  and the animated edges on the topology.
- **Notifications** are what the café's code chooses to say about the
  business: an order came in, the oat milk ran out. Only component code
  publishes one, with a topic, a payload, and optionally a summary for
  people. Each publisher declares its topics with `@Publisher`: `take_order`
  the four in the table above, `Restock` `pantry.restocked`.

`Kitchen` shows the other side. It is a `@Subscriber("kitchen.ticket")`, so
it gets each ticket through `on_notification()` without knowing who publishes
it, and its **Details** count the tickets it has received. Those tickets have
no summary, so they never reach the UI.

`Counter` hands each order to `take_order` instead of handling it inside its
own `run()` loop. That way every order is a call of its own, logged and shown
on its own, with its notifications pointing back to it.

## Structure

```
26-notifications/
├── config.toml           # [service.counter] interval: seconds between orders
├── main.py               # alternative to `odf run` — boots the same UI via odf.server.Server directly
└── app/
    ├── __init__.py       # imports every module so decorators register at startup
    ├── entities.py       # Order(id, table, item), Supply(id, name, stock) — @Entity
    ├── repositories.py   # Orders, Pantry — @Storage @Repository, in-memory
    ├── functions.py      # take_order(table, item) — @Publisher @Function publishing the notifications
    ├── services.py       # Counter — @Service taking the next order every few seconds
    ├── components.py     # Kitchen — @Subscriber @Component receiving kitchen.ticket
    └── tasks.py          # Restock — @Publisher @Task refilling the pantry
```

## Run it

```bash
cd examples/26-notifications
odf run
```

or `python main.py`, which boots the same UI. Watch the notices come in, then
click **Execute** on `Restock` once the oat milk is out.
