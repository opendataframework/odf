import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from opendataframework.context import Context
from starlette.websockets import WebSocketDisconnect

from odf.ui.origin import OriginCheck
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
