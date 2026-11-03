"""Keeps the chat's conversations with the assistant in a JSON sidecar file.

Two kinds of conversation share the file, told apart by their key:

- ``assistant/<id>``: a conversation started from the drawer's **Assistant**,
  listed and reopened by its ``id``, and titled by its first message;
- ``<channel>/<thread>``: the one conversation held inside a channel's thread
  (see ``odf.ui.conversations``), shown in the thread as notes between its
  messages and cards.

Only what was said is kept, a turn being ``{"role", "content", "ts"}`` with
``role`` ``"user"`` or ``"assistant"``. A turn's tool calls aren't: they're
in the logs, and in **Show run**. Each conversation keeps its latest
``limit`` turns. A thread's messages and cards aren't copied here; they're
read from their repositories.

Nothing here knows who is asking, so a conversation is shared by everyone
using the UI. Scoped to whatever ``Path`` a ``UiServer`` is constructed with,
like ``odf.ui.annotations`` (see ``Server.start``'s ``chat-file`` and
``chat-history`` config keys). The file holds::

    {
      "version": 1,
      "conversations": {
        "assistant/3f2a9c…": {
          "title": "Why is Thursday's bake sheet so big?",
          "updated": 1793700004.2,
          "turns": [
            {"role": "user", "content": "Why is…", "ts": 1793700000.0},
            {"role": "assistant", "content": "Because…", "ts": 1793700004.2}
          ]
        },
        "restaurants/Le Petit": {"updated": 1793701006.8, "turns": [...]}
      }
    }
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path

VERSION = 1
ASSISTANT = "assistant"
# How much of a conversation's first message titles it.
_TITLE = 60
_ROLES = ("user", "assistant")


def thread_key(channel: str, thread: str) -> str:
    """Return the key of the conversation held inside ``thread`` of ``channel``."""
    return f"{channel}/{thread}"


def assistant_key(conversation_id: str) -> str:
    """Return the key of the assistant conversation ``conversation_id``."""
    return f"{ASSISTANT}/{conversation_id}"


class ChatHistory:
    """Reads and writes the conversations file, one change at a time.

    Every change is load-modify-write on the whole file, under a lock, since
    the UI's routes run on FastAPI's thread pool.

    Args:
        path: Location of the JSON file. Parent directories are created as
            needed.
        limit: How many of a conversation's latest turns are kept. Must be at
            least 1.
    """

    def __init__(self, path: str | Path, limit: int) -> None:
        """Store where the file is and how much of each conversation to keep."""
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        self.path = Path(path)
        self.limit = limit
        self._lock = threading.Lock()

    def conversations(self) -> list[dict]:
        """List the assistant conversations, the one changed last first.

        Returns:
            ``[{"id", "title", "updated", "turns"}]``, ``turns`` being how
            many there are.
        """
        data = self._load()
        found = []
        for key, conversation in data["conversations"].items():
            kind, _, conversation_id = key.partition("/")
            if kind != ASSISTANT:
                continue
            found.append(
                {
                    "id": conversation_id,
                    "title": conversation.get("title", ""),
                    "updated": conversation.get("updated", 0),
                    "turns": len(conversation.get("turns", [])),
                }
            )
        return sorted(found, key=lambda c: c["updated"], reverse=True)

    def turns(self, key: str) -> list[dict]:
        """Return a conversation's turns, oldest first, or ``[]`` if there's none yet."""
        conversation = self._load()["conversations"].get(key)
        return list(conversation.get("turns", [])) if conversation else []

    def get(self, key: str) -> dict | None:
        """Return a conversation, or ``None`` if there's no such one."""
        conversation = self._load()["conversations"].get(key)
        return dict(conversation) if conversation else None

    def new_id(self) -> str:
        """Return an id for a new assistant conversation."""
        return uuid.uuid4().hex

    def append(self, key: str, turns: list[dict]) -> None:
        """Add ``turns`` to a conversation, starting it if it's new.

        An assistant conversation is titled by its first user turn. Only the
        latest ``limit`` turns are kept.

        Args:
            key: ``assistant_key(id)`` or ``thread_key(channel, thread)``.
            turns: ``{"role", "content"}`` dicts, with ``ts`` when known.

        Raises:
            ValueError: If a turn's ``role`` isn't ``"user"`` or
                ``"assistant"``, or its ``content`` isn't a string.
        """
        now = time.time()
        clean = []
        for turn in turns:
            if turn.get("role") not in _ROLES or not isinstance(turn.get("content"), str):
                raise ValueError(f"not a chat turn: {turn!r}")
            clean.append(
                {"role": turn["role"], "content": turn["content"], "ts": turn.get("ts", now)}
            )
        if not clean:
            return
        with self._lock:
            data = self._load()
            conversation = data["conversations"].setdefault(key, {"turns": []})
            if key.startswith(f"{ASSISTANT}/") and not conversation.get("title"):
                first = next((t["content"] for t in clean if t["role"] == "user"), "")
                conversation["title"] = " ".join(first.split())[:_TITLE]
            conversation["turns"] = [*conversation.get("turns", []), *clean][-self.limit :]
            conversation["updated"] = clean[-1]["ts"]
            self._save(data)

    def delete(self, key: str) -> bool:
        """Delete a conversation. Returns whether there was one."""
        with self._lock:
            data = self._load()
            if data["conversations"].pop(key, None) is None:
                return False
            self._save(data)
            return True

    def _load(self) -> dict:
        """Return the saved document, or an empty one if the file is absent.

        Raises:
            ValueError: If the file exists but isn't a JSON object, rather
                than reading it as empty and replacing it on the next save.
        """
        try:
            raw = self.path.read_text()
        except FileNotFoundError:
            return {"version": VERSION, "conversations": {}}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.path} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{self.path} does not hold a JSON object")
        data.setdefault("version", VERSION)
        data.setdefault("conversations", {})
        return data

    def _save(self, data: dict) -> None:
        """Write the document, replacing any existing file atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.replace(tmp, self.path)
