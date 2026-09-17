"""Optional MCP server: exposes the same actions as the dev UI over MCP.

Not a DI-managed ``Service`` — like ``UiServer``, it introspects the container
from the outside, so it is constructed and driven directly by
``Server.start(mcp=True)`` / ``Server.stop()``, after the ``Context`` has
already resolved. Lets any MCP-speaking client (an LLM agent, Claude Desktop,
...) start/stop components, execute tasks/pipelines, and query repository
data that was previously only reachable by clicking through the UI.
"""

import threading
from typing import Any

try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise ImportError(
        "server.start(mcp=True) requires the 'mcp' extra. Install with: pip install odf[mcp]"
    ) from exc

from opendataframework.component import McpToolsProtocol
from opendataframework.context import Context
from opendataframework.repository import ReadableProtocol
from opendataframework.utils import kebab

from odf.ui.data import find_repository, list_records, parse_filters
from odf.ui.topology import build_topology

_MAX_QUERY_LIMIT = 500


class McpServer:
    """Exposes a single ``Context``'s actions as MCP tools over streamable HTTP.

    Runs uvicorn in a background daemon thread so ``start()`` never blocks
    the caller — mirroring ``UiServer`` and how the framework backgrounds
    ``Service.run()``.

    Args:
        context: The already-open ``Context`` to introspect and act on.
        project: Display name, used as the MCP server's own name.
        host: Interface to bind to.
        port: Port to bind to.
    """

    def __init__(
        self,
        context: Context,
        project: str,
        host: str = "127.0.0.1",
        port: int = 4748,
    ) -> None:
        """Build the FastMCP server and register every tool (see class docstring for args)."""
        self._context = context
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

        # FastMCP's constructor calls logging.basicConfig() with this level,
        # globally configuring the root logger (RichHandler included) — left
        # at its "INFO" default, that prints every request/session-manager
        # line from the mcp package and httpx to the console. Match uvicorn's
        # own log_level="warning" below so a client script's plain print()s
        # aren't drowned out by transport chatter.
        mcp = FastMCP(project, host=host, port=port, log_level="WARNING")

        @mcp.tool()
        def list_components() -> list[dict]:
            """List every resolved component, repository, service, task, and
            pipeline: its type, layer, and — for services — whether it is
            currently running. Use each entry's "label" (its class name) as
            the "name" argument to the other tools. Use a "repository"-typed
            entry's "id" as the "repo_id" argument to query_repository."""
            topology = build_topology(self._context, project)
            return [
                {k: v for k, v in node.items() if k not in ("col", "row")}
                for node in topology["nodes"]
            ]

        @mcp.tool()
        def query_repository(
            repo_id: str,
            limit: int = 50,
            offset: int = 0,
            filters: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Return a page of records from a resolved repository's data,
            with optional per-field substring filters — the same
            paged/filtered access pattern the dev UI's data table uses, so
            you can answer a question about a repository's data without
            pulling the whole dataset into context. Use list_components()'s
            "id" for a "repository"-typed entry as "repo_id" here. "filters"
            is a field-name -> substring mapping; only keys matching the
            repository's entity fields are applied (others are ignored), and
            a record matches only if every given field's stringified value
            contains its filter value, case-insensitively. "limit" is capped
            at 500. Returns {"records": [...], "total": <total matching
            count>}."""
            found = find_repository(self._context, repo_id)
            if found is None:
                raise ValueError(f"No resolved repository named {repo_id!r}")
            _, instance, entity_cls = found
            if not isinstance(instance, ReadableProtocol):
                raise ValueError(f"Repository {repo_id!r} is not readable")
            parsed_filters = parse_filters(entity_cls, (filters or {}).items())
            records, total = list_records(
                instance,
                entity_cls,
                limit=min(limit, _MAX_QUERY_LIMIT),
                offset=offset,
                filters=parsed_filters,
            )
            return {"records": records, "total": total}

        @mcp.tool()
        def start_component(name: str) -> str:
            """Start a resolved Service by class name (e.g. "Postgres"). No-op
            if it is already running."""
            try:
                self._context.start(name)
            except KeyError:
                raise ValueError(f"No resolved component named {name!r}") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
            return f"{name} started"

        @mcp.tool()
        def stop_component(name: str) -> str:
            """Stop a running Service by class name (e.g. "Postgres"). No-op
            if it is not running."""
            try:
                self._context.stop(name)
            except KeyError:
                raise ValueError(f"No resolved component named {name!r}") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
            return f"{name} stopped"

        @mcp.tool(structured_output=False)
        def execute_task(name: str):
            """Execute a Task or Pipeline by class name (e.g. "SeedUsers"),
            returning whatever execute() returns. Use component_logs to see
            what it printed."""
            try:
                return self._context.execute(name)
            except KeyError:
                raise ValueError(f"No resolved component named {name!r}") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc

        @mcp.tool()
        def component_logs(name: str, lines: int = 50) -> list[dict]:
            """Return the last log entries for any resolved component, by
            class name (e.g. "Postgres")."""
            if not any(cls.__name__ == name for cls in self._context.instances):
                raise ValueError(f"No resolved component named {name!r}")
            return self._context.tail_logs(name, lines)

        # Component-exposed tools: every resolved instance implementing
        # McpToolsProtocol contributes its own tools in addition to the six
        # fixed tools above, namespaced by its kebab-case class name so they
        # can't collide with the fixed tools or with another component's
        # tools of the same local name.
        registered_names: set[str] = set()
        for cls, instance in self._context.instances.items():
            if not isinstance(instance, McpToolsProtocol):
                continue
            for tool in instance.mcp_tools():
                full_name = f"{kebab(cls.__name__)}.{tool.name}"
                if full_name in registered_names:
                    raise ValueError(f"Duplicate MCP tool name: {full_name!r}")
                registered_names.add(full_name)
                mcp.add_tool(
                    tool.handler,
                    name=full_name,
                    description=tool.description,
                    structured_output=tool.structured_output,
                )

        self._mcp = mcp
        self._app = mcp.streamable_http_app()

    @property
    def mcp(self) -> FastMCP:
        """The underlying ``FastMCP`` instance, for in-process tool reuse (e.g. chat)."""
        return self._mcp

    @property
    def url(self) -> str:
        """The MCP endpoint URL (streamable HTTP transport)."""
        return f"http://{self._host}:{self._port}{self._mcp.settings.streamable_http_path}"

    def start(self) -> None:
        """Start serving in a background daemon thread. Returns immediately."""
        config = uvicorn.Config(self._app, host=self._host, port=self._port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the server to exit and wait for the background thread to finish."""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
