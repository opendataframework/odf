import time
import urllib.error
import urllib.request

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from opendataframework.context import Context
from starlette.websockets import WebSocketDisconnect

from odf.ui.origin import HostCheck, OriginCheck
from odf.ui.server import UiServer


@pytest.fixture
def client():
    """A ``TestClient`` over a UI, reached at ``http://testserver``."""
    with Context(namespaces=set()) as ctx:
        yield TestClient(UiServer(ctx, "proj")._app)


def test_request_without_origin_passes(client):
    assert client.put("/api/layout", json={}).status_code == 204


def test_request_from_the_uis_own_origin_passes(client):
    r = client.put("/api/layout", json={}, headers={"Origin": "http://testserver"})

    assert r.status_code == 204


def test_request_from_the_host_a_proxy_forwarded_passes(client):
    r = client.put(
        "/api/layout",
        json={},
        headers={"Origin": "https://odf.example.com", "X-Forwarded-Host": "odf.example.com"},
    )

    assert r.status_code == 204


@pytest.mark.parametrize("origin", ["https://evil.example.com", "http://testserver:8080", "null"])
def test_request_from_another_origin_is_refused(client, origin):
    r = client.put("/api/layout", json={}, headers={"Origin": origin})

    assert r.status_code == 403
    assert "Cross-site request refused" in r.json()["detail"]


def test_safe_request_from_another_origin_passes(client):
    r = client.get("/api/topology", headers={"Origin": "https://evil.example.com"})

    assert r.status_code == 200


def websocket_app() -> FastAPI:
    """An app behind ``OriginCheck`` with an echoing WebSocket."""
    app = FastAPI()
    app.add_middleware(OriginCheck)

    @app.websocket("/proxy/app/ws")
    async def echo(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(await websocket.receive_text())
        await websocket.close()

    return app


def test_websocket_from_the_uis_own_origin_is_accepted():
    client = TestClient(websocket_app())

    with client.websocket_connect("/proxy/app/ws", headers={"Origin": "http://testserver"}) as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "hi"


def test_websocket_from_another_origin_is_refused():
    client = TestClient(websocket_app())

    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(
            "/proxy/app/ws", headers={"Origin": "https://evil.example.com"}
        ):
            pass

    assert refused.value.code == 1008


def host_checked_app(host: str) -> HostCheck:
    """An app with a page and an echoing WebSocket, behind ``HostCheck`` bound to ``host``."""
    app = websocket_app()

    @app.get("/page")
    def page() -> dict:
        return {}

    return HostCheck(app, host)


@pytest.mark.parametrize(
    "base_url", ["http://127.0.0.1:4747", "http://localhost:4747", "http://[::1]:4747"]
)
def test_loopback_bound_ui_answers_loopback_hosts(base_url):
    client = TestClient(host_checked_app("127.0.0.1"), base_url=base_url)

    assert client.get("/page").status_code == 200


@pytest.mark.parametrize("base_url", ["http://evil.example.com", "http://evil.example.com:4747"])
def test_loopback_bound_ui_refuses_another_host(base_url):
    client = TestClient(host_checked_app("127.0.0.1"), base_url=base_url)

    r = client.get("/page")

    assert r.status_code == 421
    assert "X-Forwarded-Host" in r.json()["detail"]


def test_loopback_bound_ui_refuses_a_websocket_for_another_host():
    client = TestClient(host_checked_app("127.0.0.1"), base_url="http://evil.example.com")

    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/proxy/app/ws"):
            pass

    assert refused.value.code == 1008


def test_ui_bound_beyond_loopback_answers_any_host():
    client = TestClient(host_checked_app("0.0.0.0"), base_url="http://evil.example.com")  # nosec B104

    assert client.get("/page").status_code == 200


@pytest.fixture
def served_ui():
    """A UI served on a real port, bound to ``127.0.0.1``."""
    with Context(namespaces=set()) as ctx:
        ui = UiServer(ctx, "proj", port=18780)
        ui.start()
        try:
            yield ui
        finally:
            ui.stop()


def send(ui, method: str, headers: dict[str, str]) -> int:
    """The status of ``method /api/layout`` on the served UI, sent with ``headers``."""
    request = urllib.request.Request(
        f"{ui.local_url}/api/layout",
        data=b"{}" if method == "PUT" else None,
        method=method,
        headers={"Content-Type": "application/json", **headers},
    )
    for _ in range(50):
        try:
            with urllib.request.urlopen(request, timeout=1) as res:
                return res.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except OSError:
            time.sleep(0.1)
    raise AssertionError("UI server never became ready")


def test_served_ui_refuses_a_rebound_host(served_ui):
    assert send(served_ui, "GET", {"Host": "evil.example.com"}) == 421


def test_served_ui_answers_a_reverse_proxy(served_ui):
    status = send(
        served_ui,
        "PUT",
        {"X-Forwarded-Host": "odf.example.com", "Origin": "https://odf.example.com"},
    )

    assert status == 204
