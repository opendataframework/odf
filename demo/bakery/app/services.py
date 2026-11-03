"""The integrations that run all the time: webhooks pushed in, a mailbox polled, a drive watched,
and a scheduler.

Each one only gets the data in and hands every item to a function in
``app.ingest``. That function saves it and publishes a notification, as one
call per item.
"""

import json
import poplib
import threading
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated

from opendataframework import Config, Logger, Service

from app import layers
from app.clients import Clock, Drive, Mail, Messenger, Pos
from app.ingest import ingest_invoice, ingest_message, ingest_sale, sync_sheets
from app.pipelines import CloseCafe, NightRun, Onboard
from app.repositories import BakeSheets, CafeSales
from app.settings import setting
from app.storages import SQLite
from app.tasks import ReconcilePos


@layers.Integrations
@Service
class WebhookReceiver:
    """Receives the POS's and the messenger's webhooks, on ``[service.webhook-receiver] port``.

    Each request's signature is checked before anything is read from it. An
    order or a message is then handed to ``ingest_sale`` or ``ingest_message``,
    which take each one only once, so a webhook the tool retries does no harm.
    An error answers 500, so the tool retries later.
    """

    def __init__(
        self,
        config: Config,
        pos: Pos,
        messenger: Messenger,
        take_sale: Annotated[Callable[..., bool], ingest_sale],
        take_message: Annotated[Callable[..., int | None], ingest_message],
        logger: Logger,
    ) -> None:
        """Read where to listen; leave the service stopped.

        Args:
            config: Project config; reads ``service.webhook-receiver.host`` and ``.port``.
            pos: Verifies the POS's signatures.
            messenger: Verifies the messenger's signatures, and reads its payloads.
            take_sale: ``ingest_sale``.
            take_message: ``ingest_message``.
            logger: The service's logger.
        """
        section = config.get("service").get("webhook-receiver")
        self.address = (str(section.get("host", "0.0.0.0")), int(section.get("port", 4750)))  # nosec B104
        self.pos, self.messenger = pos, messenger
        self.take_sale, self.take_message = take_sale, take_message
        self.logger = logger
        self._server: ThreadingHTTPServer | None = None

    def handle(self, path: str, headers: Mapping[str, str], body: bytes) -> tuple[int, dict]:
        """Handle one webhook request. Returns the status code and the JSON answer."""
        if path == "/webhooks/pos":
            if not self.pos.verify(headers.get("X-Pos-Signature"), body):
                return 401, {"error": "bad signature"}
            event = json.loads(body)
            if event.get("type") != "order.created":
                return 200, {"ignored": event.get("type")}
            new = self.take_sale(event["data"]["object"])
            return 200, {"received": event["id"], "new": new}
        if path == "/webhooks/messenger":
            if not self.messenger.verify(headers.get("X-Signature-256"), body):
                return 401, {"error": "bad signature"}
            taken = [
                self.take_message("messenger", m["id"], m["from"], m["text"], m["sent"])
                for m in Messenger.inbound(json.loads(body))
            ]
            return 200, {"received": len(taken)}
        return 404, {"error": f"no webhook at {path}"}

    def setup(self) -> None:
        """Bind the port, before ``run()`` serves it."""
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            """Hands each POST to ``WebhookReceiver.handle``."""

            def do_POST(self) -> None:
                """Answer one webhook."""
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                try:
                    status, answer = receiver.handle(self.path, self.headers, body)
                except (ValueError, KeyError, TypeError) as exc:
                    status, answer = 400, {"error": f"unreadable webhook: {exc!r}"}
                except Exception as exc:  # the tool retries a 500
                    receiver.logger.error(f"webhook {self.path} failed: {exc!r}")
                    status, answer = 500, {"error": "failed, retry later"}
                data = json.dumps(answer).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                """Log requests to the service's own log, not stderr."""
                receiver.logger.debug(format % args)

        self._server = ThreadingHTTPServer(self.address, Handler)
        self.logger.info(f"listening for webhooks on port {self.address[1]}")

    def run(self) -> None:
        """Serve webhooks until ``stop()``."""
        self._server.serve_forever(poll_interval=0.5)

    def stop(self) -> None:
        """Stop serving and free the port."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def parse_email(raw: bytes) -> dict:
    """Return an email's ``id``, ``from`` address, ``name``, ``subject``, ``text`` and ``sent``.

    Also ``pdf``: its first PDF attachment as ``(filename, content)``, or ``None``.
    """
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    name, address = parseaddr(str(mail.get("From", "")))
    body = mail.get_body(preferencelist=("plain",))
    date = mail.get("Date")
    pdf = next(
        (
            (part.get_filename() or "invoice.pdf", part.get_content())
            for part in mail.iter_attachments()
            if part.get_content_type() == "application/pdf"
        ),
        None,
    )
    return {
        "pdf": pdf,
        "id": str(mail.get("Message-ID", "")).strip(),
        "from": address.lower(),
        "name": name or address,
        "subject": str(mail.get("Subject", "")),
        "text": body.get_content().replace("\r\n", "\n").strip() if body is not None else "",
        "sent": parsedate_to_datetime(str(date)).timestamp() if date else time.time(),
    }


@layers.Integrations
@Service
class Mailbox:
    """Checks the bakery's mailbox over POP3 every ``[service.mailbox] interval`` seconds.

    Messages stay on the server, as most mail clients leave them: the ones
    already taken in are remembered by their POP3 ``UIDL``. An email with
    a PDF attached is a supplier's invoice, handed to ``ingest_invoice``;
    any other, to ``ingest_message``. The very first check takes in the
    mailbox's history without announcing it. The bakery's own replies,
    which the demo's mail server also holds, are skipped.
    """

    def __init__(
        self,
        config: Config,
        sqlite: SQLite,
        mail: Mail,
        take_message: Annotated[Callable[..., int | None], ingest_message],
        take_invoice: Annotated[Callable[..., int | None], ingest_invoice],
        logger: Logger,
    ) -> None:
        """Read the mailbox's address and login; leave the service stopped.

        Args:
            config: Project config; reads ``[service.mailbox]`` (``MAIL_PASSWORD``
                for the password).
            sqlite: Where the ``UIDL``s taken in are remembered.
            mail: The bakery's own address, whose emails aren't taken in.
            take_message: ``ingest_message``.
            take_invoice: ``ingest_invoice``.
            logger: The service's logger.
        """
        section = "service.mailbox"
        self.host = setting(config, section, "host", "MAIL_HOST", "mailpit")
        self.port = int(setting(config, section, "port", "MAIL_POP3_PORT", 1110))
        self.user = setting(config, section, "user", "MAIL_USER", "bakery")
        self.password = setting(config, section, "password", "MAIL_PASSWORD", "bakery")
        self.interval = float(setting(config, section, "interval", "MAIL_INTERVAL", 5))
        self.db, self.take_message, self.logger = sqlite, take_message, logger
        self.take_invoice = take_invoice
        self.own_address = mail.address
        self._stopping = threading.Event()

    def _seen(self) -> set[str]:
        """Return the ``UIDL``s already taken in."""
        with self.db.lock:
            return {row[0] for row in self.db.conn.execute("SELECT uidl FROM mailbox_seen")}

    def _remember(self, uidl: str) -> None:
        """Remember that ``uidl`` was taken in."""
        with self.db.lock:
            self.db.conn.execute("INSERT OR IGNORE INTO mailbox_seen (uidl) VALUES (?)", (uidl,))
            self.db.conn.commit()

    def check(self) -> int:
        """Take in every email not taken in before. Returns how many."""
        seen = self._seen()
        catching_up = not seen
        box = poplib.POP3(self.host, self.port, timeout=10)
        try:
            box.user(self.user)
            box.pass_(self.password)
            new = 0
            for line in box.uidl()[1]:
                number, uidl = line.decode().split(maxsplit=1)
                if uidl in seen:
                    continue
                mail = parse_email(b"\r\n".join(box.retr(int(number))[1]))
                if mail["from"] == self.own_address:
                    self._remember(uidl)
                    continue
                if mail["pdf"] is not None:
                    self.take_invoice(
                        mail["id"] or uidl,
                        mail["from"],
                        mail["name"],
                        mail["subject"],
                        *mail["pdf"],
                        mail["sent"],
                        announce=not catching_up,
                    )
                    self._remember(uidl)
                    new += 1
                    continue
                self.take_message(
                    "email",
                    mail["id"] or uidl,
                    mail["from"],
                    mail["text"],
                    mail["sent"],
                    subject=mail["subject"],
                    announce=not catching_up,
                )
                self._remember(uidl)
                new += 1
            return new
        finally:
            box.quit()

    def setup(self) -> None:
        """Get ready to check, before ``run()`` starts."""
        self._stopping.clear()

    def run(self) -> None:
        """Check the mailbox every ``interval`` seconds until ``stop()``."""
        while not self._stopping.is_set():
            try:
                self.check()
            except (OSError, poplib.error_proto) as exc:
                self.logger.warning(f"mailbox check failed: {exc!r}")
            self._stopping.wait(self.interval)

    def stop(self) -> None:
        """Stop checking."""
        self._stopping.set()


@layers.Integrations
@Service
class SharedDrive:
    """Watches the shared drive's sheets, and imports them again when one changes.

    A sheet nothing has been imported from yet, such as one the demo added
    after the bakery was onboarded, is imported quietly when it starts.
    """

    # The table each sheet is imported into.
    TABLES = {
        "products.csv": "products",
        "restaurants.csv": "restaurants",
        "standing_orders.csv": "standing_orders",
        "contracts.csv": "contracts",
        "ingredients.csv": "ingredients",
        "recipes.csv": "recipes",
        "allergens.csv": "allergens",
    }

    def __init__(
        self,
        config: Config,
        drive: Drive,
        sqlite: SQLite,
        sync: Annotated[Callable[..., dict], sync_sheets],
        logger: Logger,
    ) -> None:
        """Read how often to look; leave the service stopped.

        Args:
            config: Project config; reads ``service.shared-drive.interval``.
            drive: The shared drive.
            sqlite: To tell which sheets have been imported.
            sync: ``sync_sheets``.
            logger: The service's logger.
        """
        self.interval = float(config.get("service").get("shared-drive").get("interval", 5))
        self.drive, self.db, self.sync, self.logger = drive, sqlite, sync, logger
        self._versions: dict[str, float] = {}
        self._stopping = threading.Event()

    def never_imported(self) -> list[str]:
        """Return the sheets on the drive whose table is still empty."""
        found = []
        with self.db.lock:
            for sheet in self.drive.versions():
                table = self.TABLES.get(sheet)
                query = f"SELECT 1 FROM {table} LIMIT 1"  # nosec B608: a name from TABLES
                if table and self.db.conn.execute(query).fetchone() is None:
                    found.append(sheet)
        return found

    def catch_up(self) -> None:
        """Import the sheets quietly if one was never imported."""
        missing = self.never_imported()
        if missing:
            self.logger.info(f"importing sheets never imported: {', '.join(missing)}")
            self.sync(announce=False)

    def setup(self) -> None:
        """Note the sheets as they are now; only later changes are imported."""
        self._versions = self.drive.versions()
        self._stopping.clear()

    def run(self) -> None:
        """Catch up, then look every ``interval`` seconds until ``stop()``, importing changes."""
        try:
            self.catch_up()
        except (OSError, KeyError, ValueError) as exc:
            self.logger.warning(f"couldn't import the sheets: {exc!r}")
        while not self._stopping.wait(self.interval):
            versions = self.drive.versions()
            if versions != self._versions:
                self._versions = versions
                try:
                    self.sync()
                except (OSError, KeyError, ValueError) as exc:
                    self.logger.warning(f"couldn't import the sheets: {exc!r}")

    def stop(self) -> None:
        """Stop watching."""
        self._stopping.set()


@layers.Integrations
@Service
class Scheduler:
    """Runs what's due on the demo clock: onboarding once, then the day's runs.

    Each day, at ``CLOSE_CAFE_AT`` the café closes (leftovers, then the
    specials draft), at ``NIGHT_RUN_AT`` tomorrow is planned, and at
    ``RECONCILE_AT`` the POS is reconciled. A run is due once a day, from
    its time on, so starting the demo late in the day runs what it missed.
    The time comes from ``Clock``, so a faster demo clock runs them sooner.
    """

    CLOSE_CAFE_AT = "15:00"
    NIGHT_RUN_AT = "21:00"
    RECONCILE_AT = "23:30"

    def __init__(
        self,
        clock: Clock,
        onboard: Onboard,
        close_cafe: CloseCafe,
        night_run: NightRun,
        reconcile: ReconcilePos,
        sales: CafeSales,
        sheets: BakeSheets,
        logger: Logger,
    ) -> None:
        """Store what it runs; leave the service stopped.

        Args:
            clock: The demo clock.
            onboard: Run once, on a bakery with no sales yet.
            close_cafe: Run each day at ``CLOSE_CAFE_AT``.
            night_run: Run each day at ``NIGHT_RUN_AT``; also plans today
                once, if there's no bake sheet for it yet.
            reconcile: Run each night at ``RECONCILE_AT``.
            sales: To tell whether onboarding has happened.
            sheets: To tell whether today has been planned.
            logger: The service's logger.
        """
        self.clock, self.onboard, self.reconcile = clock, onboard, reconcile
        self.close_cafe, self.night_run = close_cafe, night_run
        self.sales, self.sheets, self.logger = sales, sheets, logger
        self._done: dict[str, str] = {}
        self._stopping = threading.Event()

    def due(self, now: datetime) -> list[str]:
        """Return the runs due at ``now`` that haven't run today: ``"close-cafe"`` and so on."""
        today = now.date().isoformat()
        times = {
            "close-cafe": self.CLOSE_CAFE_AT,
            "night-run": self.NIGHT_RUN_AT,
            "pos-reconcile": self.RECONCILE_AT,
        }
        return [
            name
            for name, at in times.items()
            if now.strftime("%H:%M") >= at and self._done.get(name) != today
        ]

    def setup(self) -> None:
        """Get ready, before ``run()`` starts."""
        self._stopping.clear()

    def run(self) -> None:
        """Onboard if needed, then check every few seconds what's due, until ``stop()``.

        A tool that can't be reached is logged and tried again later, rather
        than stopping the scheduler.
        """
        onboarded = self.sales.count_orders() > 0
        runs = {
            "close-cafe": self.close_cafe.execute,
            "night-run": self.night_run.execute,
            "pos-reconcile": self.reconcile.execute,
        }
        while not self._stopping.is_set():
            try:
                if not onboarded:
                    self.onboard.execute()
                    onboarded = True
                now = self.clock.now()
                today = now.date()
                if self._done.get("today") != today.isoformat():
                    # A first day: the bakery baked before odf, so plan it as if it had.
                    if today.isoformat() not in self.sheets.dates():
                        self.night_run.plan(today)
                    self._done["today"] = today.isoformat()
                for name in self.due(now):
                    runs[name]()
                    self._done[name] = today.isoformat()
            except OSError as exc:
                self.logger.warning(f"a tool couldn't be reached, trying again: {exc!r}")
            self._stopping.wait(5)

    def stop(self) -> None:
        """Stop scheduling."""
        self._stopping.set()
