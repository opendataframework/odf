"""Refusing what another site makes the browser send to the UI.

odf has no login of its own: a deployed UI sits behind a reverse proxy that
does it, and that login is a cookie (or cached credentials) the browser
sends with every request to the UI, including those a page on another site
makes it send. ``OriginCheck`` refuses those requests when they could change
something: a request whose method isn't a safe one, and every WebSocket
(``/proxy/<name>/``'s included), when the browser says it comes from an
origin other than the one the UI was reached by.

A request without an ``Origin`` passes: browsers send one with every
cross-origin request that could change something and with every WebSocket,
so one without comes from a script, curl, or the Jupyter subprocess saving
notebooks through the UI.

A page can also rebind its own name to ``127.0.0.1``, and then its requests
to a UI on this machine are, to the browser, same-origin ones, which
``OriginCheck`` lets through. ``HostCheck`` refuses those: a UI bound to a
loopback address only answers requests whose ``Host`` is a loopback name,
as FastMCP does for the MCP server. A reverse proxy in front of such a UI
passes the browser's host on as ``X-Forwarded-Host``.
"""

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# The names a server bound to a loopback address is reached by, without the port.
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def public_hosts(headers: Headers) -> set[str]:
    """The hosts the browser reached the UI by.

    That is ``Host``, and ``X-Forwarded-Host`` behind a reverse proxy, as
    ``host[:port]`` in lower case.
    """
    hosts = {headers.get("host"), *headers.get("x-forwarded-host", "").split(",")}
    return {h.strip().lower() for h in hosts if h and h.strip()}


async def _refuse(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
    """Answer ``status`` with ``detail``, or close a WebSocket before it's accepted."""
    if scope["type"] == "websocket":
        await WebSocket(scope, receive, send).close(code=1008)
    else:
        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)


class OriginCheck:
    """ASGI middleware refusing requests another site's page sent.

    An HTTP request with an unsafe method answers 403, and a WebSocket is
    closed before it's accepted (which the browser sees as 403), when its
    ``Origin`` isn't one of ``public_hosts``.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap ``app``."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on to the app, unless it's refused."""
        checked = scope["type"] == "websocket" or (
            scope["type"] == "http" and scope["method"] not in _SAFE_METHODS
        )
        if checked:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin is not None and urlsplit(origin).netloc.lower() not in public_hosts(headers):
                detail = (
                    f"Cross-site request refused: Origin {origin!r} isn't the host the UI "
                    f"was reached by ({headers.get('host')!r}). Behind a reverse proxy, pass "
                    "the browser's host on as X-Forwarded-Host."
                )
                await _refuse(scope, receive, send, 403, detail)
                return
        await self.app(scope, receive, send)


class HostCheck:
    """ASGI middleware refusing requests for another host, when bound to loopback.

    With ``host`` a loopback address, an HTTP request answers 421, and a
    WebSocket is closed before it's accepted, when its ``Host`` (whatever
    the port) isn't a loopback name. Bound to any other address, everything
    passes.

    Args:
        app: The app to wrap.
        host: The address the server binds to.
    """

    def __init__(self, app: ASGIApp, host: str) -> None:
        """Wrap ``app`` (see class docstring for args)."""
        self.app = app
        self._active = host in _LOOPBACK

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on to the app, unless it's refused."""
        if self._active and scope["type"] in ("http", "websocket"):
            host = Headers(scope=scope).get("host")
            if not host or urlsplit(f"//{host}").hostname not in _LOOPBACK:
                detail = (
                    f"Host {host!r} refused: the UI is bound to a loopback address, so it "
                    "only answers 127.0.0.1, localhost and [::1]. Behind a reverse proxy, "
                    "leave Host to the proxy and pass the browser's host as X-Forwarded-Host."
                )
                await _refuse(scope, receive, send, 421, detail)
                return
        await self.app(scope, receive, send)
