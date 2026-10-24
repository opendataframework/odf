"""Jupyter's authentication, by a token only the UI's proxy sends.

Loaded only inside the Jupyter subprocess ``odf.ui.notebooks.NotebookServer``
launches, which names ``ProxyIdentityProvider`` as its identity provider.

Jupyter's own token is one the browser holds: its pages hand it to the
frontend, which sends it as ``Authorization: token ...`` with every request.
Behind a reverse proxy whose login is Basic auth, that header replaces the
browser's credentials, and the proxy refuses the request. So here the
browser holds no token at all: the UI's proxy adds one to every request it
forwards (``odf.ui.notebooks.TOKEN_HEADER``), and Jupyter accepts only those.
The browser's own login is whatever stands in front of the UI.
"""

import hmac

from jupyter_server.auth.identity import IdentityProvider, User
from traitlets import Unicode, default

from odf.ui.notebooks import TOKEN_HEADER


class ProxyIdentityProvider(IdentityProvider):
    """Accepts a request only when it carries the token the UI's proxy adds."""

    proxy_token = Unicode("", config=True, help="The token the UI's proxy sends.")

    @default("token")
    def _token_default(self) -> str:
        # Nothing for Jupyter's pages to hand the browser.
        return ""

    @property
    def login_available(self) -> bool:
        """No login page: the browser can't sign in to Jupyter, only the proxy can."""
        return False

    def get_user(self, handler) -> User | None:
        """The UI's user for a request the proxy forwarded, ``None`` for any other."""
        return User("odf") if self._from_proxy(handler) else None

    def is_token_authenticated(self, handler) -> bool:
        """Whether the request carries the proxy's token, as every one through the UI does."""
        return self._from_proxy(handler)

    def _from_proxy(self, handler) -> bool:
        sent = handler.request.headers.get(TOKEN_HEADER, "")
        return bool(self.proxy_token) and hmac.compare_digest(sent, self.proxy_token)
