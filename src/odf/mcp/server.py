"""Optional MCP server: exposes the same actions as the dev UI over MCP.

Not a DI-managed ``Service`` — like ``UiServer``, it introspects the container
from the outside, so it is constructed and driven directly by
``Server.start(mcp=True)`` / ``Server.stop()``, after the ``Context`` has
already resolved. Lets any MCP-speaking client (an LLM agent, Claude Desktop,
...) start/stop components, execute tasks/pipelines, invoke agents, call
functions, and query
repository data that was previously only reachable by clicking through the UI.
"""

import inspect
import threading
from collections.abc import Callable
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

from odf.ui import arguments, keys
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
            """List every resolved component, repository, service, task,
            pipeline, agent, and function: its type, layer, and — for services —
            whether it is currently running. Each entry's "id" is its key,
            "<namespace>.<name>" (e.g. "service.postgres"): pass it as the
            "key" argument to the other tools. An entry with a "verb" takes
            arguments, through its own "<id>.<verb>" tool: an agent's
            "<id>.invoke", a function's "<id>.call"."""
            topology = build_topology(self._context, project)
            return [
                {k: v for k, v in node.items() if k not in ("col", "row")}
                for node in topology["nodes"]
            ]

        @mcp.tool()
        def query_repository(
            key: str,
            limit: int = 50,
            offset: int = 0,
            filters: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            """Return a page of records from a resolved repository's data,
            with optional per-field substring filters — the same
            paged/filtered access pattern the dev UI's data table uses, so
            you can answer a question about a repository's data without
            pulling the whole dataset into context. Use list_components()'s
            "id" for a "repository"-typed entry as "key" here. "filters"
            is a field-name -> substring mapping; only keys matching the
            repository's entity fields are applied (others are ignored), and
            a record matches only if every given field's stringified value
            contains its filter value, case-insensitively. "limit" is capped
            at 500. Returns {"records": [...], "total": <total matching
            count>}."""
            cls = self._lookup(key)
            found = find_repository(self._context, keys.name_of(self._context.key(cls)))
            if found is None or found[0] is not cls:
                raise ValueError(f"{key!r} is not a repository")
            _, instance, entity_cls = found
            if not isinstance(instance, ReadableProtocol):
                raise ValueError(f"Repository {key!r} is not readable")
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
        def start_component(key: str) -> str:
            """Start a resolved Service by key (e.g. "service.postgres").
            No-op if it is already running."""
            try:
                self._context.start(key)
            except KeyError:
                raise self._missing(key, "a Service") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
            return f"{key} started"

        @mcp.tool()
        def stop_component(key: str) -> str:
            """Stop a running Service by key (e.g. "service.postgres").
            No-op if it is not running."""
            try:
                self._context.stop(key)
            except KeyError:
                raise self._missing(key, "a Service") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
            return f"{key} stopped"

        @mcp.tool(structured_output=False)
        def execute_task(key: str):
            """Execute a Task or Pipeline by key (e.g. "task.seed-users"),
            returning whatever execute() returns. Use component_logs to see
            what it printed."""
            try:
                return self._context.execute(key)
            except KeyError:
                raise self._missing(key, "a Task or Pipeline") from None
            except TypeError as exc:
                raise ValueError(str(exc)) from exc

        @mcp.tool()
        def component_logs(key: str, lines: int = 50) -> list[dict]:
            """Return the last log entries for any resolved component, by
            key (e.g. "service.postgres")."""
            return self._context.tail_logs(self._context.key(self._lookup(key)), lines)

        # Component-exposed tools: everything that takes arguments gets a
        # tool named by its verb (an agent's "invoke", a function's "call";
        # see odf.ui.arguments), and every resolved instance implementing
        # McpToolsProtocol contributes its own tools, in addition to the six
        # fixed tools above. Both are prefixed by the component's key so they can't
        # collide with the fixed tools or with another component's tools of
        # the same local name.
        registered_names: set[str] = set()
        for kind, entry in arguments.ENTRIES.items():
            for obj in arguments.callables(self._context, kind):
                full_name = f"{self._context.key(obj)}.{entry.verb}"
                registered_names.add(full_name)
                mcp.add_tool(
                    self._call_handler(obj),
                    name=full_name,
                    description=arguments.describe(obj),
                    structured_output=False,
                )
        for cls, instance in self._context.instances.items():
            if not isinstance(instance, McpToolsProtocol):
                continue
            for tool in instance.mcp_tools():
                full_name = f"{self._context.key(cls)}.{tool.name}"
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

    def _missing(self, key: str, expected: str) -> ValueError:
        """Return the error for ``key`` naming no resolved instance of ``expected``.

        The ``Context`` reports a function's key there as unknown, since a
        function has no instance; say what it is instead.
        """
        if keys.lookup(self._context, key) is not None:
            return ValueError(f"{key} is not {expected}")
        return ValueError(f"No resolved component with key {key!r}")

    def _lookup(self, key: str) -> type | Callable[..., object]:
        """Return the resolved class or function addressed by ``key``.

        Raises:
            ValueError: If ``key`` is not ``<namespace>.<name>``, or names no
                resolved class or function.
        """
        cls = keys.lookup(self._context, key)
        if cls is None:
            raise ValueError(f"No resolved component with key {key!r}")
        return cls

    def _call_handler(self, obj: type | Callable[..., object]):
        """Return a tool handler that calls ``obj`` through ``Context.call()``.

        Its signature is the arguments ``obj`` takes (see
        ``odf.ui.arguments``), so FastMCP builds the tool's input schema from
        its own annotations.
        """

        def call(**kwargs):
            """Call the object through the context, with ``kwargs`` as its arguments."""
            return self._context.call(self._context.key(obj), **kwargs)

        call.__signature__ = inspect.Signature(arguments.parameters(self._context, obj))
        return call

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
