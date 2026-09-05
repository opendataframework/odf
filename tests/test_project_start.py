import os
import signal
import sys
import threading
import time
import urllib.request
import warnings

import pytest
from opendataframework.context import Context
from opendataframework.namespace import Namespace

from odf.server import Server


def make_ns():
    class NS(Namespace): ...

    return NS


# --- UI ---------------------------------------------------------------


def test_start_ui_true_serves_topology_over_http():
    server = Server(context=Context(namespaces=set()))
    server.start(ui=True, ui_port=18765, app_module=None)
    try:
        assert server.ui_url == "http://127.0.0.1:18765"

        last_err = None
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{server.ui_url}/api/topology", timeout=1) as res:
                    assert res.status == 200
                    break
            except OSError as e:
                last_err = e
                time.sleep(0.1)
        else:
            raise AssertionError(f"UI server never became ready: {last_err}")
    finally:
        server.stop()


def test_stop_clears_ui_url():
    server = Server(context=Context(namespaces=set()))
    server.start(ui=True, ui_port=18766, app_module=None)
    server.stop()
    assert server.ui_url is None


# --- MCP server -------------------------------------------------------------------


def test_start_mcp_true_serves_tools_over_http():
    import asyncio

    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    server = Server(context=Context(namespaces=set()))
    server.start(mcp=True, mcp_port=18767, app_module=None)
    try:
        assert server.mcp_url == "http://127.0.0.1:18767/mcp"

        async def list_tools():
            async with streamable_http_client(server.mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.list_tools()

        tools = last_err = None
        for _ in range(50):
            try:
                tools = asyncio.run(list_tools())
                break
            except Exception as e:
                last_err = e
                time.sleep(0.1)
        else:
            raise AssertionError(f"MCP server never became ready: {last_err}")

        names = {t.name for t in tools.tools}
        assert {"list_components", "start_component", "stop_component", "execute_task"} <= names
    finally:
        server.stop()


def test_stop_clears_mcp_url():
    server = Server(context=Context(namespaces=set()))
    server.start(mcp=True, mcp_port=18768, app_module=None)
    server.stop()
    assert server.mcp_url is None


# --- wait() / run() -----------------------------------------------------


def test_wait_blocks_until_sigint_then_stops():
    server = Server(context=Context(namespaces=set()))
    server.start(app_module=None)

    def send_sigint():
        time.sleep(0.2)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=send_sigint, daemon=True).start()
    start = time.monotonic()
    server.wait()
    assert time.monotonic() - start < 2


def test_wait_blocks_until_sigterm_then_stops():
    server = Server(context=Context(namespaces=set()))
    server.start(app_module=None)

    def send_sigterm():
        time.sleep(0.2)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=send_sigterm, daemon=True).start()
    start = time.monotonic()
    server.wait()
    assert time.monotonic() - start < 2


def test_stop_from_another_thread_unblocks_wait():
    server = Server(context=Context(namespaces=set()))
    server.start(app_module=None)

    threading.Thread(target=lambda: (time.sleep(0.2), server.stop()), daemon=True).start()
    start = time.monotonic()
    server.wait()
    assert time.monotonic() - start < 2


def test_run_starts_then_blocks_until_stopped():
    server = Server(context=Context(namespaces=set()))

    threading.Thread(target=lambda: (time.sleep(0.2), server.stop()), daemon=True).start()
    server.run(ui=True, ui_port=18769, app_module=None)
    assert server.ui_url is None


# --- zero-component warning ----------------------------------------------


def test_start_warns_when_zero_components_registered():
    server = Server(context=Context(namespaces=set()))
    with pytest.warns(UserWarning, match="zero application components"):
        server.start(app_module=None)
    server.stop()


def test_start_warns_even_when_config_is_preseeded():
    # Context always pre-seeds a Config singleton whenever config= is
    # passed (opendataframework.context.Context.__init__) — the check must
    # not treat that as "a component," or this warning would never fire
    # for Server.from_config/from_dict, the one construction path (odf
    # run, most examples) the warning is meant to catch.
    ctx = Context(namespaces=set(), config={})
    server = Server(context=ctx)
    with pytest.warns(UserWarning, match="zero application components"):
        server.start(app_module=None)
    server.stop()


def test_start_does_not_warn_when_a_component_is_registered():
    NS = make_ns()

    @NS
    class Widget:
        pass

    server = Server(context=Context(namespaces={NS}))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        server.start(app_module=None)
    server.stop()


def test_start_with_missing_app_module_does_not_raise_but_warns():
    server = Server(context=Context(namespaces=set()))
    with pytest.warns(UserWarning, match="zero application components"):
        server.start(app_module="odf_test_definitely_missing_module")
    server.stop()


# --- app_module auto-import -----------------------------------------------


def test_start_auto_imports_app_module_by_default(tmp_path, monkeypatch):
    # Uses a fresh Namespace defined inside the fixture app.py, rather than
    # a builtin one (Component/Repository/...), so this test can't collide
    # with real components other test files may have permanently
    # registered into those shared, process-lifetime namespaces.
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "app.py").write_text(
        "from opendataframework.namespace import Namespace\n"
        "\n"
        "class OdfTestNS(Namespace): ...\n"
        "\n"
        "@OdfTestNS\n"
        "class OdfTestAutoImportWidget:\n"
        "    pass\n"
    )
    try:
        import app

        server = Server(context=Context(namespaces={app.OdfTestNS}, config={}))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            server.start()  # app_module defaults to "app"
        assert "app" in sys.modules
        assert len(server.context.instances) == 2  # OdfTestAutoImportWidget + Config
        server.stop()
    finally:
        for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
            sys.modules.pop(name, None)


def test_start_with_app_module_none_skips_auto_import(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "app.py").write_text("raise RuntimeError('should never be imported')\n")

    server = Server(context=Context(namespaces=set()))
    with pytest.warns(UserWarning, match="zero application components"):
        server.start(app_module=None)
    assert "app" not in sys.modules
    server.stop()
