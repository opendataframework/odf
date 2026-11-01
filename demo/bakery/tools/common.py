"""What the simulated tools share: the demo clock, HTTP calls, webhook signing and delivery,
and a plain page shell for their UIs."""

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

WORLD_URL = os.environ.get("WORLD_URL", "http://world:8000")


def env(name: str, default: str) -> str:
    """Return environment variable ``name``, or ``default`` when it's unset or empty."""
    return os.environ.get(name) or default


def data_dir() -> Path:
    """Return the directory a tool keeps its database in (``DATA_DIR``, default ``./data``)."""
    path = Path(env("DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def sign(secret: str, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``body`` under ``secret``."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def http_json(
    method: str, url: str, payload: object = None, headers: dict | None = None, timeout: float = 5
) -> object:
    """Send ``payload`` as JSON and return the decoded JSON answer (``None`` if empty).

    Raises:
        OSError: If the request fails or answers with an error status.
    """
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def sim_now() -> datetime:
    """Return the demo clock's time, from ``world``, or real local time if it's unreachable."""
    try:
        return datetime.fromisoformat(http_json("GET", f"{WORLD_URL}/clock", timeout=2)["now"])
    except OSError, ValueError, KeyError, TypeError:
        return datetime.now().replace(microsecond=0)


def wait_for(url: str, attempts: int = 60) -> None:
    """Wait until ``url`` answers at all, for up to ``attempts`` seconds."""
    for _ in range(attempts):
        try:
            urllib.request.urlopen(url, timeout=2).close()
            return
        except urllib.error.HTTPError:
            return  # it answered, if with an error
        except OSError:
            time.sleep(1)


class Outbox:
    """Webhook deliveries, kept in SQLite and retried with backoff until they succeed.

    That's how a vendor sends webhooks: each event is signed and POSTed to the
    subscriber's URL, and retried a few times when the subscriber is down. A
    delivery can also be dropped, which is what the "missed webhook" scenario
    does: the event exists in the tool, but never reaches the subscriber.

    Args:
        db: The tool's database connection.
        lock: The lock guarding ``db``.
        url: Where deliveries go.
        headers_for: Returns the headers for a body (its signature, say).
    """

    RETRIES = 6

    def __init__(
        self,
        db: sqlite3.Connection,
        lock: threading.Lock,
        url: str,
        headers_for: Callable[[bytes], dict],
    ) -> None:
        """See class docstring for args."""
        self.db, self.lock, self.url, self.headers_for = db, lock, url, headers_for
        with self.lock:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, body BLOB NOT NULL,"
                " attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL,"
                " status TEXT NOT NULL, error TEXT, created REAL NOT NULL)"
            )
            self.db.commit()
        self._stopping = threading.Event()

    def add(self, event_id: str, payload: dict, *, drop: bool = False) -> None:
        """Queue ``payload`` for delivery, or record it as dropped."""
        now = time.time()
        with self.lock:
            self.db.execute(
                "INSERT OR IGNORE INTO outbox (id, body, next_at, status, created)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    event_id,
                    json.dumps(payload).encode(),
                    now,
                    "dropped" if drop else "pending",
                    now,
                ),
            )
            self.db.commit()

    def deliver_due(self) -> None:
        """Send every pending delivery whose time has come, once."""
        with self.lock:
            due = self.db.execute(
                "SELECT id, body, attempts FROM outbox WHERE status = 'pending' AND next_at <= ?"
                " ORDER BY created",
                (time.time(),),
            ).fetchall()
        for event_id, body, attempts in due:
            request = urllib.request.Request(self.url, data=body, method="POST")
            request.add_header("Content-Type", "application/json")
            for key, value in self.headers_for(body).items():
                request.add_header(key, value)
            try:
                urllib.request.urlopen(request, timeout=5).close()
                status, error = "delivered", None
            except OSError as exc:
                status = "failed" if attempts + 1 >= self.RETRIES else "pending"
                error = str(exc)
            with self.lock:
                self.db.execute(
                    "UPDATE outbox SET status = ?, attempts = ?, next_at = ?, error = ?"
                    " WHERE id = ?",
                    (status, attempts + 1, time.time() + 2 ** (attempts + 1), error, event_id),
                )
                self.db.commit()

    def recent(self, limit: int = 15) -> list[dict]:
        """Return the latest deliveries, newest first."""
        with self.lock:
            rows = self.db.execute(
                "SELECT id, status, attempts, error FROM outbox ORDER BY created DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"id": r[0], "status": r[1], "attempts": r[2], "error": r[3]} for r in rows]

    def start(self) -> None:
        """Deliver in a background thread, checking once a second, until ``stop()``."""

        def loop() -> None:
            while not self._stopping.wait(1):
                self.deliver_due()

        threading.Thread(target=loop, daemon=True).start()

    def stop(self) -> None:
        """Stop delivering."""
        self._stopping.set()


def connect(name: str) -> tuple[sqlite3.Connection, threading.Lock]:
    """Open the tool's own SQLite database, ``<DATA_DIR>/<name>.db``, with a lock to share it."""
    db = sqlite3.connect(data_dir() / f"{name}.db", check_same_thread=False)
    return db, threading.Lock()


PAGE_STYLE = """
:root{color-scheme:light dark;--bg:#f6f5f2;--panel:#fff;--text:#222;--muted:#666;--line:#ddd;
--accent:#2d6a4f}
@media (prefers-color-scheme:dark){:root{--bg:#18191b;--panel:#222326;--text:#e8e8e8;
--muted:#9a9a9a;--line:#333;--accent:#74c69d}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);
color:var(--text)}header{padding:12px 16px;border-bottom:1px solid var(--line);
background:var(--panel);display:flex;gap:12px;align-items:baseline}
header h1{font-size:16px;margin:0}header small{color:var(--muted)}main{padding:16px;
display:grid;gap:16px;max-width:1100px}.panel{background:var(--panel);border:1px solid var(--line);
border-radius:8px;padding:12px}.panel h2{font-size:13px;margin:0 0 8px;color:var(--muted);
text-transform:uppercase;letter-spacing:.04em}button{font:inherit;padding:6px 10px;
border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--text);
cursor:pointer}button:hover{border-color:var(--accent)}button.primary{background:var(--accent);
color:#fff;border-color:var(--accent)}input,select,textarea{font:inherit;padding:6px 8px;
border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text)}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:4px 6px;
border-bottom:1px solid var(--line);font-size:13px}.muted{color:var(--muted)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
"""


def page(title: str, subtitle: str, body: str) -> str:
    """Return a full HTML page: the shared plain style, a header, and ``body``."""
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{PAGE_STYLE}</style></head><body>"
        f"<header><h1>{title}</h1><small>{subtitle}</small></header><main>{body}</main>"
        "</body></html>"
    )
