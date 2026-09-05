"""Builds editable repository/record data from a resolved ``Context``.

Pure introspection and coercion, mirroring ``ui/topology.py``'s shape: no
HTTP concerns live here, only functions that ``ui/server.py`` wires to
routes. Nothing here touches the DI container or drives lifecycle.

Only repositories whose entity is a ``dataclass`` are exposed — field names
and types come from ``dataclasses.fields()``, and there is no other
structured way to describe an entity's shape today. The dataclass's first
field is treated as the identifier: ``Entity`` has no explicit primary-key
metadata, so this is a convention (matches ``User(id, name, email)``), not a
guarantee.
"""

import dataclasses
import types
import typing
from collections.abc import Iterable
from typing import Any

from opendataframework.context import Context
from opendataframework.repository import (
    ReadableProtocol,
    Repository,
    StreamableProtocol,
    WritableProtocol,
)
from opendataframework.utils import kebab
from opendataframework.view import (
    AudioView,
    DataView,
    DataViewProtocol,
    DocumentView,
    ImageView,
    LocationView,
    ReplayProtocol,
    StreamingAudioView,
    StreamingVideoView,
    TableView,
    TimeseriesView,
    VideoView,
)


def build_repositories(context: Context) -> list[dict]:
    """Describe every resolved, dataclass-entity-backed repository.

    Args:
        context: A ``Context`` that has already been opened.

    Returns:
        A list of JSON-serializable repository schemas.
    """
    repo_classes = set(dict(Repository.items()).values())
    schemas = []
    for cls, instance in context.instances.items():
        if cls not in repo_classes:
            continue
        entity = Repository.entity(cls)
        if entity is None or not dataclasses.is_dataclass(entity):
            continue
        schemas.append(_describe_repository(context, cls, entity, instance))
    return schemas


def find_repository(context: Context, repo_id: str) -> tuple[type, object, type] | None:
    """Look up a repository by its topology id (kebab-case class name).

    Args:
        context: A ``Context`` that has already been opened.
        repo_id: The kebab-case id, as used by ``ui/topology.py`` node ids.

    Returns:
        ``(repo_cls, instance, entity_cls)``, or ``None`` if no resolved,
        dataclass-entity-backed repository matches.
    """
    repo_classes = set(dict(Repository.items()).values())
    for cls, instance in context.instances.items():
        if cls not in repo_classes or kebab(cls.__name__) != repo_id:
            continue
        entity = Repository.entity(cls)
        if entity is None or not dataclasses.is_dataclass(entity):
            continue
        return cls, instance, entity
    return None


def parse_filters(entity_cls: type, query_params: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Pick out entity-field filters from a request's raw query params.

    Args:
        entity_cls: The dataclass entity type, used to whitelist which query
            param keys are actually filterable fields — anything else
            (``limit``, ``offset``, an unrelated param) is ignored rather
            than raising, since the UI's per-column filter inputs are the
            only intended caller.
        query_params: The request's raw ``(key, value)`` pairs (e.g.
            Starlette's ``QueryParams.items()``), kept as a plain iterable
            of strings so this module stays free of any HTTP framework type.

    Returns:
        A ``{field_name: needle}`` mapping, empty values dropped.
    """
    field_names = {f.name for f in dataclasses.fields(entity_cls)}
    return {key: value for key, value in query_params if key in field_names and value != ""}


def list_records(
    instance: ReadableProtocol,
    entity_cls: type,
    *,
    limit: int | None = None,
    offset: int = 0,
    filters: dict[str, str] | None = None,
) -> tuple[list[dict], int]:
    """Return a page of entities from ``instance.all()`` as plain dicts.

    ``ReadableProtocol`` only exposes ``all()`` — there is no lower-level
    paged/filtered fetch to push ``limit``/``offset``/``filters`` into, so
    both are applied by filtering and slicing the full result here.

    Args:
        instance: A repository implementing ``ReadableProtocol``.
        entity_cls: The dataclass entity type it manages.
        limit: Maximum number of records to return, or ``None`` (the
            default) to return every record — preserves the pre-pagination
            behavior for callers (image/media/document views) that need the
            whole set. The map and timeseries views also paginate now, one
            page of markers/chart data at a time, rather than fetching the
            whole repository at once. Replay mode (see ``ReplayProtocol``)
            also relies on this ``None`` full-fetch path — it caches the
            whole record set client-side once, on entering replay, rather
            than adding a server-side time-range query.
        offset: Number of records to skip before the returned page.
        filters: A ``{field_name: needle}`` mapping (see ``parse_filters``).
            A record matches only if every field's stringified value
            contains its needle, case-insensitively — simple substring
            filtering rather than type-aware comparisons, so it works
            uniformly across str/int/float/bool fields without risking a
            coercion error on partial input.

    Returns:
        ``(records, total)`` — the page of JSON-serializable dicts, and the
        total record count across the whole filtered (but unpaginated)
        collection.
    """
    all_entities = instance.all()
    if filters:
        all_entities = [e for e in all_entities if _matches_filters(e, filters)]
    total = len(all_entities)
    page = all_entities[offset : offset + limit] if limit is not None else all_entities
    return [to_json_safe_dict(entity) for entity in page], total


def _matches_filters(entity: Any, filters: dict[str, str]) -> bool:
    return all(
        needle.lower() in str(getattr(entity, field, "")).lower()
        for field, needle in filters.items()
    )


def to_json_safe_dict(entity: Any) -> dict:
    """``dataclasses.asdict()``, with any raw ``bytes`` fields dropped.

    Media fields (an image/audio/video clip) aren't JSON-serializable and
    are never read off this dict anyway — the UI fetches them separately via
    the dedicated ``.../media`` endpoint, keyed by the entity's id.
    """
    return {k: (None if isinstance(v, bytes) else v) for k, v in dataclasses.asdict(entity).items()}


def key_field_name(entity_cls: type) -> str:
    """Return the identifier field's name — the entity dataclass's first field."""
    return dataclasses.fields(entity_cls)[0].name


def resolve_view(instance: object, *, readable: bool) -> DataView | None:
    """Resolve the single dev-UI view for a resolved repository instance.

    An explicit ``DataViewProtocol.data_view()`` always wins. Otherwise, a
    readable repository (the caller has already filtered to a dataclass
    entity) falls back to the implicit default: a plain ``TableView`` of
    every field. A repository that's neither gets no view at all.
    """
    if isinstance(instance, DataViewProtocol):
        return instance.data_view()
    return TableView() if readable else None


def resolve_replay_field(instance: object, view: DataView | None) -> str | None:
    """Resolve the timestamp field a repository's records can be replayed by, if any.

    A ``TimeseriesView`` is always replayable via its own ``field`` — no opt-in
    needed. Otherwise, an explicit ``ReplayProtocol.replay_field()`` opts a
    ``LocationView``/``VideoView``/``AudioView`` repository in. Everything else
    (``TableView``, ``ImageView``, ``DocumentView``, the streaming views) has no
    replay concept in the dev UI today.
    """
    if isinstance(view, TimeseriesView):
        return view.field
    if isinstance(instance, ReplayProtocol):
        return instance.replay_field()
    return None


def build_entity(entity_cls: type, data: dict, *, key: str, key_value: Any) -> Any:
    """Construct ``entity_cls`` from form data, forcing the identifier field.

    Args:
        entity_cls: The dataclass entity type to construct.
        data: Raw field values (e.g. from a JSON request body).
        key: The name of the identifier field.
        key_value: The value to force onto the identifier field — ``None``
            to create, or an already-coerced value to update.

    Returns:
        A new ``entity_cls`` instance.
    """
    field_types = {f.name: f.type for f in dataclasses.fields(entity_cls)}
    kwargs = {
        name: _coerce(value, field_types[name])
        for name, value in data.items()
        if name in field_types and name != key
    }
    kwargs[key] = key_value
    return entity_cls(**kwargs)


def coerce_key(entity_cls: type, key_field: str, raw_key: str) -> Any:
    """Coerce a path-param identifier to the identifier field's type.

    Args:
        entity_cls: The dataclass entity type.
        key_field: The name of the identifier field.
        raw_key: The raw string value taken from the URL path.

    Returns:
        ``raw_key`` coerced to the identifier field's declared type.
    """
    field_type = next(f.type for f in dataclasses.fields(entity_cls) if f.name == key_field)
    return _coerce(raw_key, field_type)


def _describe_repository(context: Context, cls: type, entity: type, instance: object) -> dict:
    fields = dataclasses.fields(entity)
    readable = isinstance(instance, ReadableProtocol)
    streamable = isinstance(instance, StreamableProtocol)
    view = resolve_view(instance, readable=readable)
    return {
        "id": kebab(cls.__name__),
        "label": cls.__name__,
        "entity": entity.__name__,
        "key": key_field_name(entity),
        "fields": [{"name": f.name, "type": _type_name(f.type)} for f in fields],
        "readable": readable,
        "writable": isinstance(instance, WritableProtocol),
        "streamable": streamable,
        "streaming": streamable and context.is_streaming(cls.__name__),
        "view": _view_dict(view) if view is not None else None,
        "replay_field": resolve_replay_field(instance, view),
    }


def _view_dict(view: DataView) -> dict:
    """Serialize a ``DataView`` to a JSON-safe, discriminated dict.

    Every variant becomes ``{"kind": ..., **its own field(s)}`` — one ``kind``
    string per ``DataView`` subclass, so the UI can dispatch on a single key.
    """
    if isinstance(view, TableView):
        return {"kind": "table", "fields": list(view.fields) if view.fields is not None else None}
    if isinstance(view, ImageView):
        return {"kind": "image", "field": view.field}
    if isinstance(view, StreamingVideoView):
        return {"kind": "streaming-video", "field": view.field}
    if isinstance(view, VideoView):
        return {"kind": "video", "field": view.field}
    if isinstance(view, StreamingAudioView):
        return {"kind": "streaming-audio", "field": view.field}
    if isinstance(view, AudioView):
        return {"kind": "audio", "field": view.field}
    if isinstance(view, DocumentView):
        return {"kind": "document", "field": view.field}
    if isinstance(view, LocationView):
        return {"kind": "location", "fields": list(view.fields)}
    if isinstance(view, TimeseriesView):
        return {"kind": "timeseries", "field": view.field}
    raise TypeError(f"Unknown DataView variant: {view!r}")


def _unwrap_optional(field_type: Any) -> Any:
    """Strip a ``X | None`` / ``Optional[X]`` union down to ``X``."""
    origin = typing.get_origin(field_type)
    if origin is typing.Union or origin is types.UnionType:
        args = [a for a in typing.get_args(field_type) if a is not type(None)]
        if args:
            return args[0]
    return field_type


def _type_name(field_type: Any) -> str:
    resolved = _unwrap_optional(field_type)
    return getattr(resolved, "__name__", str(resolved))


def _coerce(value: Any, field_type: Any) -> Any:
    """Coerce a raw (str/JSON-native) value toward a dataclass field's type.

    Covers ``int``, ``float``, ``bool``, ``str``, and ``X | None`` —
    sufficient for form input from the dev UI, not a general codec.
    """
    if value is None:
        return None
    resolved = _unwrap_optional(field_type)
    if resolved is bool and isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if resolved in (int, float) and isinstance(value, str) and value == "":
        return None
    if resolved in (int, float, str):
        return resolved(value)
    return value
