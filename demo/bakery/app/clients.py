"""Clients for the bakery's existing tools: their APIs, their webhook signatures, the shared drive.

Each is an ``@Integrations @Component`` holding one tool's address and credentials, so
the rest of the project never handles a token or a URL itself.
"""

import csv
import hashlib
import hmac
import json
import smtplib
import time
import urllib.request
from collections.abc import Iterator
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from pathlib import Path
from urllib.parse import urlencode

from opendataframework import Component, Config

from app import layers
from app.settings import setting


def _request(method: str, url: str, token: str, payload: object = None) -> object:
    """Call a tool's JSON API with a bearer token, and return the decoded answer."""
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
        return json.loads(response.read() or b"null")


def _hmac(secret: str, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``body``."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@layers.Integrations
@Component
class Clock:
    """The demo clock: simulated time from the world service, or real time without one."""

    def __init__(self, config: Config) -> None:
        """Read ``[component.clock] world-url`` (``WORLD_URL`` overrides).

        Args:
            config: Project config.
        """
        self.url = setting(config, "component.clock", "world-url", "WORLD_URL", "")

    def now(self) -> datetime:
        """Return the simulated time, or the real local time if the world can't be reached."""
        if self.url:
            try:
                with urllib.request.urlopen(f"{self.url}/clock", timeout=2) as r:  # nosec B310
                    return datetime.fromisoformat(json.load(r)["now"])
            except OSError, ValueError, KeyError:
                pass
        return datetime.now().replace(microsecond=0)

    def details(self) -> dict[str, str]:
        """Show the time the bakery is working to."""
        return {"now": self.now().strftime("%A %d %B, %H:%M"), "source": self.url or "real time"}


@layers.Integrations
@Component
class Pos:
    """The café POS: its order API, and the signature on its webhooks."""

    # Seconds a webhook's signature stays valid, against replays.
    TOLERANCE = 300

    def __init__(self, config: Config) -> None:
        """Read ``[component.pos]``; ``POS_URL``, ``POS_TOKEN``, ``POS_WEBHOOK_SECRET`` override.

        Args:
            config: Project config.
        """
        self.url = setting(config, "component.pos", "url", "POS_URL", "http://pos:8001")
        self.token = setting(config, "component.pos", "token", "POS_TOKEN", "pos-dev-token")
        self.secret = setting(
            config, "component.pos", "webhook-secret", "POS_WEBHOOK_SECRET", "pos-dev-secret"
        )

    def verify(self, signature: str | None, body: bytes, now: float | None = None) -> bool:
        """Return whether ``X-Pos-Signature`` (``t=<unix>,v1=<hex>``) signs ``body``, recently."""
        try:
            parts = dict(item.split("=", 1) for item in (signature or "").split(","))
            sent = int(parts["t"])
        except KeyError, ValueError:
            return False
        if abs((now or time.time()) - sent) > self.TOLERANCE:
            return False
        expected = _hmac(self.secret, f"{sent}.".encode() + body)
        return hmac.compare_digest(expected, parts.get("v1", ""))

    def orders(self, created_after: str | None = None) -> Iterator[dict]:
        """Yield every order, oldest first, page by page."""
        cursor = None
        while True:
            query = {"limit": 500}
            if created_after:
                query["created_after"] = created_after
            if cursor:
                query["cursor"] = cursor
            page = _request("GET", f"{self.url}/v1/orders?{urlencode(query)}", self.token)
            yield from page["orders"]
            cursor = page.get("next_cursor")
            if not cursor:
                return


@layers.Integrations
@Component
class Messenger:
    """The business messenger: its webhook signature, its history, and sending replies."""

    def __init__(self, config: Config) -> None:
        """Read ``[component.messenger]``; ``MESSENGER_*`` variables override.

        Args:
            config: Project config.
        """
        section = "component.messenger"
        self.url = setting(config, section, "url", "MESSENGER_URL", "http://messenger:8002")
        self.token = setting(config, section, "token", "MESSENGER_TOKEN", "messenger-dev-token")
        self.secret = setting(
            config, section, "app-secret", "MESSENGER_APP_SECRET", "messenger-dev-secret"
        )
        self.phone_id = setting(
            config, section, "phone-number-id", "MESSENGER_PHONE_ID", "100200300"
        )

    def verify(self, signature: str | None, body: bytes) -> bool:
        """Return whether ``X-Signature-256`` (``sha256=<hex>``) signs ``body``."""
        expected = "sha256=" + _hmac(self.secret, body)
        return hmac.compare_digest(expected, signature or "")

    @staticmethod
    def inbound(payload: dict) -> list[dict]:
        """Return a webhook body's text messages: ``{"id", "from", "name", "text", "sent"}``."""
        found = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                names = {
                    c.get("id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])
                }
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    found.append(
                        {
                            "id": message["id"],
                            "from": message["from"],
                            "name": names.get(message["from"]) or message["from"],
                            "text": message["text"]["body"],
                            "sent": float(message["timestamp"]),
                        }
                    )
        return found

    def history(self, since: str | None = None) -> list[dict]:
        """Return the messages the bakery has exchanged, oldest first."""
        query = f"?{urlencode({'since': since})}" if since else ""
        return _request("GET", f"{self.url}/v1/{self.phone_id}/messages{query}", self.token)[
            "messages"
        ]

    def send(self, to: str, text: str) -> str:
        """Send ``text`` to ``to`` from the bakery's number. Returns the message id."""
        answer = _request(
            "POST",
            f"{self.url}/v1/{self.phone_id}/messages",
            self.token,
            {"to": to, "type": "text", "text": {"body": text}},
        )
        return answer["messages"][0]["id"]


@layers.Integrations
@Component
class Drive:
    """The shared drive's folder, where the bakery keeps its spreadsheets as CSV."""

    SHEETS = (
        "products.csv",
        "restaurants.csv",
        "standing_orders.csv",
        "contracts.csv",
        "ingredients.csv",
        "recipes.csv",
        "allergens.csv",
    )

    def __init__(self, config: Config) -> None:
        """Read ``[component.drive] path`` (``SHARED_DRIVE`` overrides).

        Args:
            config: Project config.
        """
        self.path = Path(setting(config, "component.drive", "path", "SHARED_DRIVE", "shared-drive"))

    def rows(self, sheet: str) -> list[dict]:
        """Return a sheet's rows, as dicts by column; empty if the sheet isn't there."""
        path = self.path / sheet
        if not path.exists():
            return []
        with path.open(newline="") as f:
            return list(csv.DictReader(f))

    def versions(self) -> dict[str, float]:
        """Return each sheet's last-modified time; a missing sheet is left out."""
        return {s: (self.path / s).stat().st_mtime for s in self.SHEETS if (self.path / s).exists()}


@layers.Integrations
@Component
class Weather:
    """The weather forecast, from an Open-Meteo-style API (the world serves one, offline)."""

    def __init__(self, config: Config) -> None:
        """Read ``[component.weather]``: ``url`` (``WEATHER_URL`` overrides), ``lat``, ``lon``.

        Args:
            config: Project config.
        """
        section = "component.weather"
        self.url = setting(config, section, "url", "WEATHER_URL", "")
        self.lat = float(setting(config, section, "lat", "WEATHER_LAT", 51.454))
        self.lon = float(setting(config, section, "lon", "WEATHER_LON", -2.592))

    def daily(self, day: date) -> dict[str, float] | None:
        """Return ``{"rain_mm", "temp_max"}`` forecast for ``day``, or ``None`` if there's none.

        The forecast is only a factor in the café's forecast, so a weather
        service that's down leaves it out rather than failing the night run.
        """
        if not self.url:
            return None
        query = urlencode(
            {
                "latitude": self.lat,
                "longitude": self.lon,
                "daily": "precipitation_sum,temperature_2m_max",
                "start_date": day.isoformat(),
                "end_date": day.isoformat(),
            }
        )
        try:
            with urllib.request.urlopen(f"{self.url}/v1/forecast?{query}", timeout=5) as r:  # nosec B310
                daily = json.load(r)["daily"]
            return {
                "rain_mm": float(daily["precipitation_sum"][0]),
                "temp_max": float(daily["temperature_2m_max"][0]),
            }
        except OSError, ValueError, KeyError, IndexError, TypeError:
            return None

    def details(self) -> dict[str, str]:
        """Show where the forecast comes from."""
        return {"source": self.url or "none", "location": f"{self.lat}, {self.lon}"}


@layers.Integrations
@Component
class Mail:
    """Sending email from the bakery's address, over SMTP."""

    def __init__(self, config: Config) -> None:
        """Read ``[component.mail]``: ``host``, ``port`` and ``address`` (``MAIL_*`` override).

        Args:
            config: Project config.
        """
        section = "component.mail"
        self.host = setting(config, section, "host", "MAIL_HOST", "mailpit")
        self.port = int(setting(config, section, "port", "MAIL_SMTP_PORT", 1025))
        self.address = setting(
            config, section, "address", "MAIL_ADDRESS", "orders@bakery.example"
        ).lower()
        self.name = setting(config, section, "name", "MAIL_NAME", "The Bakery")

    def send(self, to: str, subject: str, text: str) -> str:
        """Email ``text`` to ``to``. Returns the email's ``Message-ID``."""
        mail = EmailMessage()
        mail["From"] = formataddr((self.name, self.address))
        mail["To"] = to
        mail["Subject"] = subject
        mail["Date"] = format_datetime(datetime.now().astimezone())
        mail["Message-ID"] = make_msgid(domain=self.address.split("@")[-1])
        mail.set_content(text)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(mail)
        return mail["Message-ID"]
