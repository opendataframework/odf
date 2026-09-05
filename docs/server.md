# Server

`odf.server.Server` wraps an `opendataframework.Project` and adds the
optional UI, MCP server, and chat orchestration that need third-party
dependencies. `odf run` (see [CLI](cli.md)) is a thin wrapper around
exactly this class — use `Server` directly when you want to boot a
project from Python instead: embedded in a larger application, a test
fixture, a notebook, or any process that isn't the `odf` CLI.

## A minimal app

Every `Server` is built around two things: a `config.toml` and an `app`
package that registers components as a side effect of being imported —
the same layout `odf init` scaffolds.

```toml
# config.toml
[project]
name = "my-project"
```

```python
# app/entities.py
from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Book:
    id: int | None
    title: str
    author: str
```

```python
# app/repositories.py
from opendataframework import Repository, Storage

from app.entities import Book


@Storage
@Repository(Book)
class Books:
    def __init__(self) -> None:
        self._books: list[Book] = []
```

```python
# app/__init__.py
from app import entities, repositories

__all__ = ["entities", "repositories"]
```

```python
# main.py
from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
```

```text
$ python main.py
UI running at http://127.0.0.1:4747
Press Ctrl+C to stop
```

This is exactly what
[`examples/01-table-view`](https://github.com/opendataframework/odf/tree/main/examples/01-table-view)
does — see [Examples](examples.md) for more.

## The `app` module

Decorator registration (`@Entity`, `@Repository`, `@Component`, `@Service`,
`@Task`, `@Pipeline`, ...) is a side effect of the class definition
actually executing — nothing registers until the module that defines it
gets imported. `Server.start()` handles this for you: before resolving
the `Context`, it imports one entry-point module, controlled by
`app_module`.

| `app_module` | Behavior |
|---|---|
| `"app"` (default) | Import a module/package named `app` from the current working directory before resolving. Matches `odf run`'s `--app` default — a project laid out by `odf init` needs nothing extra passed. A missing `app` module is not an error; it's silently ignored, since components may already be registered some other way. |
| `"my_pkg"` | Import a differently named module/package instead — pass whatever name your entry point actually has. |
| `None` | Skip the import entirely. Use this if you've already imported your components yourself (e.g. earlier in the same script) and don't want `start()` to attempt anything on your behalf. |

The one file that actually gets imported (`app`, by default) doesn't need
to define components itself — it just needs to import whatever does, the
way `app/__init__.py` above imports `entities`/`repositories`. Anything
reachable transitively from that one import registers.

If, after resolving, zero application components were registered — no
matter why (wrong `app_module`, a module that imports but forgot to
decorate anything, or `app_module=None` with nothing registered
elsewhere) — `start()` raises a `UserWarning` rather than silently
booting an empty project:

```pycon
>>> server.start()
<stdin>:1: UserWarning: Server.start() resolved zero application
components — no module named 'app' could be imported to register them
(or app_module=None was passed). Pass app_module= to point at the
package that defines your @Entity/@Repository/@Component classes, or
import it yourself before calling start().
```

## Lifecycle

```python
server = Server.from_config("config.toml")  # or Server.from_dict({...}), or Server(...)

server.start(ui=True, mcp=False, chat=False)  # non-blocking — returns immediately
server.wait()  # blocks until Ctrl+C/SIGTERM or stop()
```

- **`start(ui=, ui_host=, ui_port=, mcp=, mcp_host=, mcp_port=, chat=, app_module=)`**
  resolves the `Context` (importing `app_module` first, see above), then
  optionally starts the MCP server and UI — each backgrounded on its own
  daemon thread, like any `Service`. Always returns immediately, whether
  or not `ui=`/`mcp=` were passed, so you can do something with
  `server.ui_url`/`server.mcp_url` before ceding control of the process.
- **`wait()`** blocks the calling thread until interrupted by `Ctrl+C`
  (`SIGINT`) or `SIGTERM` (the signal process managers/containers send to
  request a clean shutdown), or until another thread calls `stop()`
  directly — then stops the server itself. Call it once you're done with
  any setup that has to happen between `start()` returning and blocking
  (printing URLs, as above); skip it entirely if you're embedding
  `Server` in something that manages its own process lifecycle.
- **`run(**same kwargs as start())`** is `start(...)` followed by
  `wait()` in one call — the one-liner for a script whose only job is to
  keep a foreground server alive:

  ```python
  Server.from_config("config.toml").run(ui=True)
  ```

- **`stop()`** tears down the UI, MCP server, and the underlying
  `Project`, in that order. Safe to call even if `start()` was never
  called, and safe to call more than once.
- **Context manager** — `with Server.from_config(...) as server:` calls
  `start()`/`stop()` (not `wait()` — the block still runs immediately;
  add your own `server.wait()` inside if you want it to block too).

## Reading the resolved graph

```python
server.context.get(Books).all()  # typed access to a resolved instance
server.context.instances  # {cls: instance} for everything resolved
server.config  # the raw config dict
```

`server.context` and `server.config` are available both before and after
`start()` — see the sibling
[`opendataframework`](https://opendataframework.github.io/opendataframework/)
docs for what `Context`/`Config` expose in full.
