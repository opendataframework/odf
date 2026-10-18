"""Apps the UI serves under its own origin, at ``/proxy/<name>/``.

A web app the UI embeds (Jupyter, for the document view's notebooks) runs
as its own server on the loopback interface, and the UI forwards
``/proxy/<name>/...`` to it, HTTP and WebSockets alike. The browser then
only ever talks to the UI: one port to expose, one origin for HTTPS, and
whatever stands in front of the UI (a reverse proxy with a login page)
stands in front of the embedded app too.

The proxied app is served under the same path prefix it's reached by
(Jupyter's ``base_url``), so paths are forwarded as they are. Its own
cross-origin checks stay in charge: ``Host`` becomes the app's, and
``Origin``/``Referer`` are rewritten to the app's origin only when they are
the UI's own, so a cross-site request still reaches the app as one.

Forwarding uses tornado's clients, which run on asyncio, so this module is
only imported when an app is proxied (tornado comes with Jupyter).
"""

import asyncio
from collections.abc import Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response, WebSocket
from starlette.websockets import WebSocketDisconnect
from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest
from tornado.websocket import websocket_connect

# Headers for one hop, never forwarded (RFC 9110 §7.6.1), plus those the
# forwarding sets itself.
_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

# Headers a WebSocket handshake sets itself.
_WEBSOCKET_HEADERS = {"sec-websocket-key", "sec-websocket-version", "sec-websocket-extensions"}

# Long enough for a request that starts a kernel.
_REQUEST_TIMEOUT = 600.0

# The largest WebSocket message taken from the app: a cell's outputs, say.
_MAX_MESSAGE_SIZE = 1024**3


def prefix(name: str) -> str:
    """The path an app proxied as ``name`` is served under."""
    return f"/proxy/{name}/"


def mount_proxy(app: FastAPI, name: str, upstream: Callable[[], str | None]) -> None:
    """Forward ``/proxy/<name>/...`` to another server, HTTP and WebSockets.

    Args:
        app: The UI's app to add the routes to.
        name: The app's name in the path.
        upstream: Returns the origin the app is served at
            (``http://127.0.0.1:<port>``), or ``None`` while it isn't
            running, which answers 503.
    """
    route = prefix(name) + "{path:path}"

    @app.api_route(route, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def forward(request: Request, path: str) -> Response:
        """Forward a request to the app and return its response."""
        origin = upstream()
        if origin is None:
            return Response(f"{name} is not running", status_code=503)
        body = await request.body()
        try:
            res = await AsyncHTTPClient().fetch(
                HTTPRequest(
                    origin + _target(request.scope),
                    method=request.method,
                    headers=_forwarded_headers(request.headers, origin),
                    body=body if request.method not in ("GET", "HEAD") else None,
                    allow_nonstandard_methods=True,
                    follow_redirects=False,
                    decompress_response=False,
                    request_timeout=_REQUEST_TIMEOUT,
                ),
                raise_error=False,
            )
        except OSError as exc:
            return Response(f"{name} is not reachable: {exc}", status_code=502)
        response = Response(res.body if request.method != "HEAD" else b"", res.code)
        for key, value in res.headers.get_all():
            if key.lower() in _HOP_HEADERS:
                continue
            if key.lower() == "location" and value.startswith(origin):
                value = value[len(origin) :]
            response.headers.append(key, value)
        return response

    @app.websocket(route)
    async def relay(websocket: WebSocket, path: str) -> None:
        """Relay a WebSocket's messages to and from the app until either side closes."""
        origin = upstream()
        if origin is None:
            await websocket.close()
            return
        headers = {
            key: value
            for key, value in _forwarded_headers(websocket.headers, origin).items()
            if key.lower() not in _WEBSOCKET_HEADERS and key.lower() != "sec-websocket-protocol"
        }
        protocols = [
            p.strip()
            for p in websocket.headers.get("sec-websocket-protocol", "").split(",")
            if p.strip()
        ]
        try:
            conn = await websocket_connect(
                HTTPRequest(
                    "ws" + origin.removeprefix("http") + _target(websocket.scope),
                    headers=headers,
                    request_timeout=_REQUEST_TIMEOUT,
                ),
                subprotocols=protocols or None,
                max_message_size=_MAX_MESSAGE_SIZE,
            )
        except HTTPClientError, OSError:
            # Refused by the app (a cross-site origin, a bad token) or not
            # reachable: closing before accepting answers the browser 403.
            await websocket.close()
            return
        await websocket.accept(subprotocol=conn.selected_subprotocol)

        async def to_app() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if message.get("bytes") is not None:
                    await conn.write_message(message["bytes"], binary=True)
                else:
                    await conn.write_message(message["text"])

        async def to_browser() -> None:
            while (message := await conn.read_message()) is not None:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)

        tasks = [asyncio.ensure_future(to_app()), asyncio.ensure_future(to_browser())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            conn.close()
            try:
                await websocket.close()
            except RuntimeError, WebSocketDisconnect:
                pass  # already closed by the browser


def _target(scope: dict) -> str:
    """The request's path and query, as the browser sent them."""
    target = scope.get("raw_path", scope["path"].encode()).decode("latin-1")
    query = scope.get("query_string", b"").decode("latin-1")
    return f"{target}?{query}" if query else target


def _forwarded_headers(headers, origin: str) -> dict[str, str]:
    """The browser's headers as the app should see them, behind ``origin``.

    ``Host`` becomes the app's own, and ``Origin``/``Referer`` too when they
    name the host the browser reached the UI by (``Host``, or
    ``X-Forwarded-Host`` behind a reverse proxy). Any other ``Origin`` or
    ``Referer`` is left for the app's cross-origin checks to refuse.
    """
    public = {headers.get("host"), *headers.get("x-forwarded-host", "").split(",")}
    public = {h.strip().lower() for h in public if h and h.strip()}
    forwarded: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _HOP_HEADERS:
            continue
        if key.lower() in ("origin", "referer"):
            url = urlsplit(value)
            if url.netloc.lower() in public:
                value = origin + value[len(f"{url.scheme}://{url.netloc}") :]
        if key.lower() in forwarded:
            forwarded[key.lower()] += ", " + value
        else:
            forwarded[key.lower()] = value
    forwarded["host"] = urlsplit(origin).netloc
    return forwarded
