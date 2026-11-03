"""Reads repositories that declare a conversation as channels of threads.

A repository implementing ``ConversationProtocol`` (``opendataframework.view``)
names a channel and, by role, the fields its records read as messages by:
the thread a record is in, its time, text, direction and sender. Every
repository naming the same channel merges into it, their records in the same
threads. A repository with no ``direction`` holds cards instead of messages:
each record shown with its actions, the functions and agents whose argument
is marked ``Annotated[..., Record(Repo)]`` (``opendataframework.repository``).

Pure introspection, mirroring ``ui/data.py``'s shape: no HTTP or MCP concerns
live here, only functions that ``ui/server.py`` and ``mcp/server.py`` wire to
a route or a tool. ``validate`` checks every declaration against the
entities, so a field that doesn't exist fails when the UI starts, not when a
thread is first opened.
"""

import dataclasses
import typing
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, get_origin

from opendataframework.context import Context
from opendataframework.repository import ReadableProtocol, Record, Repository
from opendataframework.view import Conversation, ConversationProtocol

from odf.ui import arguments, data, keys

# How many of a thread's latest items ``thread`` returns by default.
DEFAULT_LIMIT = 200
# How much of an item's text a thread's preview keeps.
_PREVIEW = 140


@dataclass(frozen=True)
class Member:
    """One repository taking part in a channel.

    Attributes:
        cls: The ``@Repository`` class.
        instance: Its resolved instance.
        entity: Its dataclass entity.
        conversation: What its ``conversation()`` declared.
        key: Its key, ``<namespace>.<name>``.
    """

    cls: type
    instance: Any
    entity: type
    conversation: Conversation
    key: str

    @property
    def cards(self) -> bool:
        """Whether its records are cards rather than messages (no ``direction``)."""
        return self.conversation.direction is None


def members(context: Context) -> list[Member]:
    """Return every resolved repository declaring a conversation, checked.

    Args:
        context: A ``Context`` that has already been opened.

    Raises:
        ValueError: If a repository's conversation names a field its entity
            lacks, or the repository isn't readable.
    """
    repo_classes = set(dict(Repository.items()).values())
    found = []
    for cls, instance in context.instances.items():
        if cls not in repo_classes or not isinstance(instance, ConversationProtocol):
            continue
        key = context.key(cls)
        entity = Repository.entity(cls)
        if entity is None or not dataclasses.is_dataclass(entity):
            raise ValueError(f"{key} declares a conversation but its entity isn't a dataclass")
        if not isinstance(instance, ReadableProtocol):
            raise ValueError(f"{key} declares a conversation but isn't readable (no all())")
        conversation = instance.conversation()
        names = {f.name for f in dataclasses.fields(entity)}
        for role in ("thread", "time", "text", "direction", "sender"):
            field = getattr(conversation, role)
            if field is not None and field not in names:
                raise ValueError(
                    f"{key}'s conversation names {role}={field!r}, "
                    f"which isn't a field of {entity.__name__}"
                )
        found.append(Member(cls, instance, entity, conversation, key))
    return found


def validate(context: Context) -> None:
    """Check every conversation and every ``Record`` argument against the entities.

    Raises:
        ValueError: If a conversation names a missing field (see
            ``members``), or a ``Record`` names a repository that isn't
            resolved or a field its entity lacks.
    """
    members(context)
    for obj, _name, record in _record_parameters(context):
        if record.repository not in context.instances:
            raise ValueError(
                f"{keys.key_of(context, obj)} marks an argument Record"
                f"({record.repository.__name__}), which isn't resolved"
            )
        entity = Repository.entity(record.repository)
        names = {f.name for f in dataclasses.fields(entity)} if entity else set()
        if record.field not in names:
            raise ValueError(
                f"{keys.key_of(context, obj)} marks an argument Record"
                f"({record.repository.__name__}, field={record.field!r}), "
                f"which isn't a field of its entity"
            )


def channels(context: Context) -> list[dict]:
    """Describe every channel and the repositories in it, by channel name.

    Returns:
        ``[{"name", "repositories": [{"id", "kind"}]}]``, ``kind`` being
        ``"messages"`` or ``"cards"``.
    """
    by_name: dict[str, list[dict]] = {}
    for member in members(context):
        kind = "cards" if member.cards else "messages"
        by_name.setdefault(member.conversation.channel, []).append({"id": member.key, "kind": kind})
    return [{"name": name, "repositories": repos} for name, repos in sorted(by_name.items())]


def channel_members(context: Context, channel: str) -> list[Member]:
    """Return the repositories in ``channel``, or an empty list if there's no such channel."""
    return [m for m in members(context) if m.conversation.channel == channel]


def threads(context: Context, channel: str) -> list[dict] | None:
    """Describe each thread in ``channel``, the one with the latest item first.

    Returns:
        ``[{"thread", "time", "count", "last": {"text", "kind", "direction"}}]``,
        or ``None`` if there's no such channel.
    """
    found = channel_members(context, channel)
    if not found:
        return None
    by_thread: dict[str, dict] = {}
    for member in found:
        conversation = member.conversation
        for record in member.instance.all():
            value = getattr(record, conversation.thread)
            if value is None:
                continue
            time = sort_time(getattr(record, conversation.time))
            entry = by_thread.setdefault(str(value), {"thread": str(value), "count": 0})
            entry["count"] += 1
            if "time" not in entry or time >= entry["time"]:
                entry["time"] = time
                entry["last"] = {
                    "text": _text(record, conversation)[:_PREVIEW],
                    "kind": "card" if member.cards else "message",
                    "direction": _direction(record, conversation),
                }
    return sorted(by_thread.values(), key=lambda e: e["time"], reverse=True)


def thread(
    context: Context, channel: str, value: str, *, limit: int = DEFAULT_LIMIT
) -> list[dict] | None:
    """Return a thread's latest ``limit`` items, oldest first.

    Every repository in the channel contributes its records whose thread
    field reads as ``value``. A message carries its ``direction`` and
    ``sender``; a card carries its ``record``, whether its text is
    ``markdown``, and its ``actions``.

    Returns:
        The items, or ``None`` if there's no such channel.
    """
    found = channel_members(context, channel)
    if not found:
        return None
    items = []
    for member in found:
        conversation = member.conversation
        key_field = data.key_field_name(member.entity)
        member_actions = actions(context, member.cls) if member.cards else []
        view = data.resolve_view(member.instance, readable=True)
        for record in member.instance.all():
            thread_value = getattr(record, conversation.thread)
            if thread_value is None or str(thread_value) != value:
                continue
            item = {
                "repository": member.key,
                "key": getattr(record, key_field),
                "time": sort_time(getattr(record, conversation.time)),
                "text": _text(record, conversation),
                "kind": "card" if member.cards else "message",
            }
            if member.cards:
                metadata = data.content_metadata(member.instance, view, record)
                item["record"] = data.to_json_safe_dict(record)
                item["markdown"] = bool(
                    metadata and metadata.content_type and "markdown" in metadata.content_type
                )
                item["actions"] = [_bound(action, record) for action in member_actions]
            else:
                item["direction"] = _direction(record, conversation)
                item["sender"] = (
                    getattr(record, conversation.sender) if conversation.sender else None
                )
            items.append(item)
    items.sort(key=lambda i: i["time"])
    return items[-limit:] if limit else items


def actions(context: Context, repository_cls: type) -> list[dict]:
    """Return the functions and agents that take one of ``repository_cls``'s records.

    One argument of each is marked ``Annotated[..., Record(repository_cls)]``.
    Its other arguments named like a field of the entity are ``prefill``:
    a consumer fills them from the record, so a person can change them
    before the action runs.

    Returns:
        ``[{"id", "href", "verb", "label", "description", "param", "field",
        "prefill"}]``, sorted by label.
    """
    entity = Repository.entity(repository_cls)
    names = {f.name for f in dataclasses.fields(entity)} if entity else set()
    found = []
    for obj, param, record in _record_parameters(context):
        if record.repository is not repository_cls:
            continue
        key = keys.key_of(context, obj)
        callers = [p.name for p in arguments.parameters(context, obj)]
        found.append(
            {
                "id": key,
                "href": keys.href(context, obj),
                "verb": arguments.verb(obj),
                "label": keys.name_of(key).replace("-", " ").capitalize(),
                "description": arguments.describe(obj),
                "param": param,
                "field": record.field,
                "prefill": [name for name in callers if name != param and name in names],
            }
        )
    return sorted(found, key=lambda a: a["label"])


def sort_time(value: object) -> float:
    """Return a record's time as a Unix time, so records of several repositories sort together.

    A number is taken as a Unix time already, a ``datetime`` as itself, and a
    string as ISO 8601.

    Raises:
        ValueError: If ``value`` is none of those.
    """
    if isinstance(value, bool):
        raise ValueError(f"can't read {value!r} as a time")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        return datetime.fromisoformat(value).timestamp()
    raise ValueError(f"can't read {value!r} as a time")


def _record_parameters(
    context: Context,
) -> list[tuple[type | Callable[..., object], str, Record]]:
    """Return ``(obj, parameter, Record)`` for every caller argument marked with a ``Record``."""
    found = []
    for kind, entry in arguments.ENTRIES.items():
        for obj in arguments.callables(context, kind):
            # An annotation that can't be resolved marks nothing, as in
            # arguments.parameters().
            try:
                hints = typing.get_type_hints(entry.target(obj), include_extras=True)
            except Exception:
                hints = {}
            for name in context.parameters(obj):
                record = _record_of(hints.get(name))
                if record is not None:
                    found.append((obj, name, record))
    return found


def _record_of(annotation: object) -> Record | None:
    """Return the ``Record`` in an ``Annotated`` annotation's metadata, if any."""
    if get_origin(annotation) is not Annotated:
        return None
    return next((item for item in annotation.__metadata__ if isinstance(item, Record)), None)


def _bound(action: dict, record: object) -> dict:
    """Return ``action`` with the values it takes from ``record``."""
    values = data.to_json_safe_dict(record)
    return {
        **action,
        "value": values.get(action["field"]),
        "prefill": {name: values.get(name) for name in action["prefill"]},
    }


def _text(record: object, conversation: Conversation) -> str:
    value = getattr(record, conversation.text)
    return "" if value is None else str(value)


def _direction(record: object, conversation: Conversation) -> str | None:
    return getattr(record, conversation.direction) if conversation.direction else None
