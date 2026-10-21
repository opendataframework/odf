# Open Data Framework CLI (`odf`)

Scaffolds and runs Open Data Framework projects, and serves them through a UI, an
MCP server and a chat window. Depends on `opendataframework` for the core
abstractions (`Entity`, `Repository`, `Component`, `Service`, `Task`, `Pipeline`,
`Agent`, `Function`, `Layer`, `Context`, `Project`) — see that package for those.

**Documentation:** <https://opendataframework.github.io/odf/>

---

# Install

```bash
pip install odf                # CLI + scaffolding only
pip install "odf[ui]"          # + UI dev server
pip install "odf[mcp]"         # + MCP server
pip install "odf[ui,chat]"     # + chat window (served by the UI)
```

`odf run` starts the UI by default, so most projects want at least `odf[ui]`.

---

# Quickstart

```bash
pip install "odf[ui]"
odf init my-project            # or --template data-analytics / data-engineering / data-science / ml / research
cd my-project
odf run                        # UI at http://127.0.0.1:4747
```

With `pip install "odf[ui,mcp,chat]"`, `odf run --mcp --chat` adds the MCP server
at `http://127.0.0.1:4748/mcp` and a chat window. The same from Python:

```python
from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True, mcp=True, chat=True)
server.wait()  # blocks until Ctrl+C/SIGTERM
```

---

# What's included

- **CLI** — `odf init` scaffolds a project from a template; `odf run` starts it.
- **UI** — the topology of every component with its actions, a view of each
  repository's data (table, map, timeseries, image, video, audio, document), and
  labelling of that data into a plain `annotations.json`.
- **MCP server** — the same actions as MCP tools, plus each agent, function and
  component's own tools.
- **Chat** — a chat window in the UI, backed by a local Ollama model, that acts
  on the project through the MCP tools.

See the [documentation](https://opendataframework.github.io/odf/) for each, and
[`examples/`](https://github.com/opendataframework/odf/tree/main/examples) for 22 small projects, one concept each.
