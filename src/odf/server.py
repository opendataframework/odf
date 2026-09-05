"""``Server`` — wraps an ``opendataframework.Project`` with UI/MCP/chat orchestration."""

import importlib
import signal
import sys
import threading
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from opendataframework.config import Config
from opendataframework.context import Context
from opendataframework.project import Project

if TYPE_CHECKING:
    from odf.mcp.server import McpServer
    from odf.ui.server import UiServer


class Server:
    """Wraps an ``opendataframework.Project`` with the optional UI,
    MCP server, and chat orchestration that requires third-party
    dependencies (see this package's ``CLAUDE.md``).

    ``Server`` composes an ``opendataframework.Project`` rather than
    subclassing it, and delegates ``.context``/``.config`` straight through.
    Use ``server.context.get(cls)`` for typed access to any resolved
    instance after ``start()`` returns.

    Args:
        context: The ``Context`` to use, forwarded to the inner ``Project``.
            If omitted, a default ``Context`` is created automatically.
        config: Raw config dict, forwarded to the inner ``Project``.

    Example:
        ::

            server = Server.from_config("config.toml")
            server.start(ui=True, mcp=True, chat=True)
            print(server.ui_url)   # http://127.0.0.1:4747
            print(server.mcp_url)  # http://127.0.0.1:4748/mcp
    """

    def __init__(
        self,
        context: Context | None = None,
        config: dict | None = None,
    ) -> None:
        """Compose a fresh inner ``Project`` (see class docstring for args)."""
        self._project = Project(context=context, config=config)
        self._ui_server: UiServer | None = None
        self._mcp_server: McpServer | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def config(self) -> dict:
        """Raw configuration dict, populated by ``from_config`` or ``from_dict``.

        Returns:
            The configuration dict, or an empty dict if no config was provided.
        """
        return self._project.config

    @property
    def context(self) -> Context:
        """The underlying ``Context`` instance.

        Available before and after ``start()``. Primarily useful for
        framework extension authors and lower-level access.

        Returns:
            The ``Context`` owned by the wrapped ``Project``.
        """
        return self._project.context

    @property
    def ui_url(self) -> str | None:
        """URL of the UI, if started via ``start(ui=True)``.

        Returns:
            The UI's base URL, or ``None`` if the UI was not started.
        """
        return self._ui_server.url if self._ui_server is not None else None

    @property
    def mcp_url(self) -> str | None:
        """URL of the MCP server, if started via ``start(mcp=True)``.

        Returns:
            The MCP server's endpoint URL, or ``None`` if it was not started.
        """
        return self._mcp_server.url if self._mcp_server is not None else None

    def start(
        self,
        ui: bool = False,
        ui_host: str = "127.0.0.1",
        ui_port: int = 4747,
        mcp: bool = False,
        mcp_host: str = "127.0.0.1",
        mcp_port: int = 4748,
        chat: bool = False,
        app_module: str | None = "app",
    ) -> None:
        """Start the wrapped ``Project`` and drive optional dev-tooling servers.

        Imports ``app_module`` (if given), calls ``Project.start()``, then
        optionally starts the MCP server and the UI on top of the now-open
        ``Context``.

        Args:
            ui: If ``True``, also start the built-in UI — a small
                FastAPI dev server (backgrounded, like any ``Service``) that
                visualizes the resolved object graph. Requires the ``ui``
                extra (``pip install odf[ui]``). Grid positions moved by
                dragging a node persist to the file named by ``[project]
                layout-file`` in config (default ``"layout.json"``, relative
                to the current working directory). The icon/color pickers can
                be extended beyond the built-in set via ``[ui] icon-scripts``
                (paths to ``.js`` files, see ``odf.ui.extensions``) and
                ``[ui.colors]`` (name → hex) in config, merged with anything
                registered by installed packages through
                ``odf.ui.extensions.register_icon_script``/``register_color``.
                The favicon and header logo can likewise be overridden via
                ``[ui] favicon`` (path to an ``.svg`` file) and ``[ui] logo``
                (path to an image file, swapped in for the built-in CSS mark).
                ``[ui] brand`` replaces the "ODF" label shown next to the
                logo and in the browser tab title, for projects that want
                their own name instead of the framework's.
            ui_host: Interface for the UI server to bind to.
            ui_port: Port for the UI server to bind to.
            mcp: If ``True``, also start an optional MCP server (backgrounded,
                like any ``Service``) exposing the same actions available in
                the UI — component start/stop, task/pipeline
                execution, and log inspection — as MCP tools for any
                MCP-speaking client. Requires the ``mcp`` extra
                (``pip install odf[mcp]``).
            mcp_host: Interface for the MCP server to bind to.
            mcp_port: Port for the MCP server to bind to.
            chat: If ``True``, also add a chat window to the UI,
                backed by a local Ollama model. Requires ``ui=True`` and the
                ``chat`` extra (``pip install odf[chat]``). If ``mcp=True``
                is also passed, the chat model gets tool-calling access to
                the same actions exposed as MCP tools (start/stop
                components, execute tasks, ...) via the running MCP server's
                in-process tool registry — otherwise it's a plain LLM chat
                window with no ability to act on the project. Connection
                parameters come from ``[project.chat]`` in config: ``model``
                (default ``"gpt-oss"``) and ``ollama-host`` (default
                ``"http://localhost:11434"``).
            app_module: Import name of the module/package that registers
                components (``@Entity``/``@Repository``/``@Component``/...)
                as a side effect of being imported — the same convention
                ``odf run``'s ``--app`` flag uses (default ``"app"``).
                Imported before ``Project.start()`` resolves the ``Context``;
                a missing module is silently ignored (this isn't the only
                way components can get registered — the caller may have
                already imported them). Pass ``None`` to skip the import
                entirely.

        Raises:
            ValueError: If a circular dependency is detected, or if
                ``chat=True`` is passed without ``ui=True``.
            ImportError: If ``ui=True``/``mcp=True``/``chat=True`` but the
                corresponding extra is not installed.

        Warns:
            UserWarning: If, after ``Project.start()``, no application
                components were resolved — usually means ``app_module``
                couldn't be imported (wrong name, or ``None`` was passed)
                and nothing else registered components either.
        """
        if chat and not ui:
            raise ValueError("chat=True requires ui=True — the chat window is served by the UI")
        self._stop_event.clear()
        if app_module is not None:
            cwd = str(Path.cwd())
            if cwd not in sys.path:
                sys.path.insert(0, cwd)
            try:
                importlib.import_module(app_module)
            except ModuleNotFoundError:
                pass
        self._project.start()
        resolved = set(self.context.instances) - {Config}
        if not resolved:
            warnings.warn(
                "Server.start() resolved zero application components — no "
                f"module named {app_module!r} could be imported to register "
                "them (or app_module=None was passed). Pass app_module= to "
                "point at the package that defines your @Entity/@Repository/"
                "@Component classes, or import it yourself before calling "
                "start().",
                stacklevel=2,
            )
        if mcp:
            from odf.mcp.server import McpServer

            self._mcp_server = McpServer(
                self.context,
                self._display_name(),
                host=mcp_host,
                port=mcp_port,
            )
            self._mcp_server.start()
        if ui:
            from odf.ui import extensions
            from odf.ui.server import UiServer

            chat_engine = None
            if chat:
                from odf.chat.engine import ChatEngine

                chat_cfg = self.config.get("project", {}).get("chat", {})
                chat_engine = ChatEngine(
                    model=chat_cfg.get("model", "gpt-oss"),
                    host=chat_cfg.get("ollama-host", "http://localhost:11434"),
                    mcp=self._mcp_server.mcp if self._mcp_server is not None else None,
                )
            ui_cfg = self.config.get("ui", {})
            icon_scripts = extensions.icon_scripts() + [
                Path(p) for p in ui_cfg.get("icon-scripts", [])
            ]
            colors = {**extensions.colors(), **ui_cfg.get("colors", {})}
            favicon = ui_cfg.get("favicon")
            logo = ui_cfg.get("logo")
            self._ui_server = UiServer(
                self.context,
                self._display_name(),
                host=ui_host,
                port=ui_port,
                layout_file=self.config.get("project", {}).get("layout-file", "layout.json"),
                chat_engine=chat_engine,
                icon_scripts=icon_scripts,
                colors=colors,
                favicon=Path(favicon) if favicon else None,
                logo=Path(logo) if logo else None,
                brand=ui_cfg.get("brand"),
            )
            self._ui_server.start()
        self._running = True

    def stop(self) -> None:
        """Tear down the UI, MCP server, and the wrapped ``Project``.

        Stops the UI and MCP server first (if running), then calls
        ``Project.stop()``. Safe to call even if ``start()`` was never
        called, and safe to call more than once — a second call is a no-op.
        """
        if not self._running:
            return
        self._running = False
        if self._ui_server is not None:
            self._ui_server.stop()
            self._ui_server = None
        if self._mcp_server is not None:
            self._mcp_server.stop()
            self._mcp_server = None
        self._project.stop()
        self._stop_event.set()

    def wait(self) -> None:
        """Block the calling thread until interrupted, then ``stop()``.

        Waits for Ctrl+C (``SIGINT``) or ``SIGTERM`` — the signal process
        managers/container runtimes send to request a clean shutdown — or
        for another thread to call ``stop()`` directly, then calls
        ``stop()`` itself (a no-op if the server was already stopped). Call
        this after ``start()``, once any interstitial setup/output the
        caller wants (e.g. printing ``server.ui_url``) is done — ``start()``
        itself stays non-blocking so embedders that don't want to cede
        control of their process can skip ``wait()`` entirely.

        Signal handlers are only installed when called from the main thread
        (the only thread Python allows this for); called from another
        thread, ``wait()`` still blocks and still responds to ``stop()``
        from elsewhere, it just won't additionally respond to a raw process
        signal.
        """
        is_main_thread = threading.current_thread() is threading.main_thread()
        previous_handlers: dict[int, object] = {}
        if is_main_thread:
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[sig] = signal.signal(sig, lambda *_: self._stop_event.set())
        try:
            self._stop_event.wait()
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            self.stop()

    def run(
        self,
        ui: bool = False,
        ui_host: str = "127.0.0.1",
        ui_port: int = 4747,
        mcp: bool = False,
        mcp_host: str = "127.0.0.1",
        mcp_port: int = 4748,
        chat: bool = False,
        app_module: str | None = "app",
    ) -> None:
        """Start the server and block until interrupted, then stop.

        Equivalent to ``start(...)`` followed by ``wait()`` — the one-call
        version for a script whose only job is to keep a foreground UI/MCP
        server alive until Ctrl+C/SIGTERM. If you need to do something
        between starting and blocking (e.g. print ``server.ui_url``), call
        ``start()`` then ``wait()`` directly instead, as ``odf run`` does.

        Args:
            Same as ``start()``.

        Raises:
            Same as ``start()`` — propagates before any blocking occurs.
        """
        self.start(
            ui=ui,
            ui_host=ui_host,
            ui_port=ui_port,
            mcp=mcp,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
            chat=chat,
            app_module=app_module,
        )
        self.wait()

    def _display_name(self) -> str:
        """Project name shown in the UI header, from config or a default."""
        return self.config.get("project", {}).get("name", "ODF Project")

    def __enter__(self) -> Server:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    @classmethod
    def from_config(cls, path: str) -> Server:
        """Create a ``Server`` from a config file or directory.

        Delegates to ``opendataframework.Project.from_config`` and wraps the
        result.

        Args:
            path: Path to a ``.toml`` config file or a directory of
                ``.toml`` files to be merged.

        Returns:
            A new ``Server`` wrapping a ``Project`` configured from the
            given path.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
        """
        return cls._wrap(Project.from_config(path))

    @classmethod
    def from_dict(cls, config: dict) -> Server:
        """Create a ``Server`` from a config dictionary.

        Delegates to ``opendataframework.Project.from_dict`` and wraps the
        result.

        Args:
            config: Mapping of configuration values, equivalent to what
                ``from_config`` would parse from a ``.toml`` file.

        Returns:
            A new ``Server`` wrapping a ``Project`` configured from the
            given dict.
        """
        return cls._wrap(Project.from_dict(config))

    @classmethod
    def _wrap(cls, project: Project) -> Server:
        """Build a ``Server`` around an already-constructed ``Project``."""
        wrapper = cls.__new__(cls)
        wrapper._project = project
        wrapper._ui_server = None
        wrapper._mcp_server = None
        wrapper._stop_event = threading.Event()
        wrapper._running = False
        return wrapper
