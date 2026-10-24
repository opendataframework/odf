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
"""

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def public_hosts(headers: Headers) -> set[str]:
    """The hosts the browser reached the UI by.

    That is ``Host``, and ``X-Forwarded-Host`` behind a reverse proxy, as
    ``host[:port]`` in lower case.
    """
    hosts = {headers.get("host"), *headers.get("x-forwarded-host", "").split(",")}
    return {h.strip().lower() for h in hosts if h and h.strip()}


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
                if scope["type"] == "websocket":
                    await WebSocket(scope, receive, send).close(code=1008)
                    return
                detail = (
                    f"Cross-site request refused: Origin {origin!r} isn't the host the UI "
                    f"was reached by ({headers.get('host')!r}). Behind a reverse proxy, pass "
                    "the browser's Host header on, or set X-Forwarded-Host."
                )
                await JSONResponse({"detail": detail}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)
