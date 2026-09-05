from dataclasses import dataclass

from opendataframework.context import Context
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.view import LocationView, TableView, TimeseriesView

from odf.ui.data import (
    build_entity,
    build_repositories,
    coerce_key,
    find_repository,
    key_field_name,
    list_records,
    parse_filters,
    resolve_replay_field,
    resolve_view,
)


def make_ns():
    """Return a fresh isolated Namespace subclass to scope Context resolution.

    Mirrors the isolation pattern used in tests/test_ui_topology.py.
    """

    class NS(Namespace): ...

    return NS


@dataclass
class Widget:
    id: int | None
    name: str


# --- build_repositories ---------------------------------------------------


def test_build_repositories_includes_dataclass_entity_repo():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return []

        def save(self, entity): ...
        def delete(self, id): ...

    with Context(namespaces={NS}) as ctx:
        schemas = build_repositories(ctx)

    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["id"] == "widgets"
    assert schema["entity"] == "Widget"
    assert schema["key"] == "id"
    assert schema["readable"] is True
    assert schema["writable"] is True
    assert schema["view"] == {"kind": "table", "fields": None}
    types_by_name = {f["name"]: f["type"] for f in schema["fields"]}
    assert types_by_name == {"id": "int", "name": "str"}


def test_build_repositories_excludes_non_dataclass_entity():
    NS = make_ns()

    class PlainEntity: ...

    @NS
    @Repository(PlainEntity)
    class Plain:
        def all(self):
            return []

    with Context(namespaces={NS}) as ctx:
        assert build_repositories(ctx) == []


def test_build_repositories_marks_read_only_repo():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class ReadOnlyWidgets:
        def all(self):
            return []

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]

    assert schema["readable"] is True
    assert schema["writable"] is False


def test_build_repositories_reports_streaming_state():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Feed:
        def stream(self):
            while True:
                yield Widget(id=1, name="A")

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]
        assert schema["streamable"] is True
        assert schema["streaming"] is False

        ctx.start_stream("Feed")
        schema = build_repositories(ctx)[0]
        assert schema["streaming"] is True

        ctx.stop_stream("Feed")


# --- find_repository --------------------------------------------------------


def test_find_repository_returns_none_for_unknown_id():
    NS = make_ns()
    with Context(namespaces={NS}) as ctx:
        assert find_repository(ctx, "nonexistent") is None


def test_find_repository_returns_match():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class Widgets:
        def all(self):
            return []

    with Context(namespaces={NS}) as ctx:
        found = find_repository(ctx, "widgets")

    assert found is not None
    repo_cls, instance, entity_cls = found
    assert repo_cls.__name__ == "Widgets"
    assert entity_cls is Widget


# --- list_records / key_field_name -----------------------------------------


def test_list_records_serializes_entities():
    class FakeRepo:
        def all(self):
            return [Widget(id=1, name="A"), Widget(id=2, name="B")]

    records, total = list_records(FakeRepo(), Widget)
    assert records == [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    assert total == 2


def test_list_records_applies_limit_and_offset():
    class FakeRepo:
        def all(self):
            return [Widget(id=i, name=str(i)) for i in range(5)]

    records, total = list_records(FakeRepo(), Widget, limit=2, offset=1)
    assert records == [{"id": 1, "name": "1"}, {"id": 2, "name": "2"}]
    assert total == 5


def test_list_records_filters_by_case_insensitive_substring():
    class FakeRepo:
        def all(self):
            return [
                Widget(id=1, name="Alpha"),
                Widget(id=2, name="Beta"),
                Widget(id=3, name="alphorn"),
            ]

    records, total = list_records(FakeRepo(), Widget, filters={"name": "alph"})
    assert records == [{"id": 1, "name": "Alpha"}, {"id": 3, "name": "alphorn"}]
    assert total == 2


def test_list_records_filters_before_paginating():
    class FakeRepo:
        def all(self):
            return [Widget(id=i, name="match" if i % 2 == 0 else "skip") for i in range(6)]

    records, total = list_records(FakeRepo(), Widget, filters={"name": "match"}, limit=2, offset=1)
    assert total == 3
    assert records == [{"id": 2, "name": "match"}, {"id": 4, "name": "match"}]


def test_list_records_filters_numeric_field_by_stringified_substring():
    class FakeRepo:
        def all(self):
            return [Widget(id=1, name="a"), Widget(id=12, name="b"), Widget(id=23, name="c")]

    records, total = list_records(FakeRepo(), Widget, filters={"id": "1"})
    assert total == 2
    assert {r["id"] for r in records} == {1, 12}


def test_parse_filters_keeps_only_known_non_empty_fields():
    params = [("name", "al"), ("id", ""), ("limit", "10"), ("bogus", "x")]
    assert parse_filters(Widget, params) == {"name": "al"}


def test_key_field_name_is_first_field():
    assert key_field_name(Widget) == "id"


# --- resolve_view -------------------------------------------------------------


@dataclass
class Store:
    id: int | None
    name: str
    lat: float
    lon: float


def test_resolve_view_falls_back_to_table_when_readable():
    class Readable:
        def all(self):
            return []

    assert resolve_view(Readable(), readable=True) == TableView()


def test_resolve_view_is_none_when_not_readable_and_no_data_view():
    class Neither: ...

    assert resolve_view(Neither(), readable=False) is None


def test_resolve_view_prefers_explicit_data_view_over_table_fallback():
    class Located:
        def all(self):
            return []

        def data_view(self):
            return LocationView(fields=("lat", "lon"))

    assert resolve_view(Located(), readable=True) == LocationView(fields=("lat", "lon"))


def test_build_repositories_reports_explicit_view():
    NS = make_ns()

    @NS
    @Repository(Store)
    class StoreLocations:
        def all(self):
            return []

        def data_view(self):
            return LocationView(fields=("lat", "lon"))

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]

    assert schema["view"] == {"kind": "location", "fields": ["lat", "lon"]}


def test_build_repositories_view_is_none_without_readable_or_data_view():
    NS = make_ns()

    @NS
    @Repository(Widget)
    class WriteOnlyWidgets:
        def save(self, entity): ...

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]

    assert schema["view"] is None


# --- resolve_replay_field -------------------------------------------------------


def test_resolve_replay_field_uses_timeseries_view_field_without_opt_in():
    assert resolve_replay_field(object(), TimeseriesView(field="created_at")) == "created_at"


def test_resolve_replay_field_uses_replay_protocol_when_implemented():
    class Replayed:
        def replay_field(self):
            return "recorded_at"

    assert resolve_replay_field(Replayed(), LocationView(fields=("lat", "lon"))) == "recorded_at"


def test_resolve_replay_field_is_none_without_opt_in():
    class Located:
        def all(self):
            return []

    assert resolve_replay_field(Located(), LocationView(fields=("lat", "lon"))) is None


def test_build_repositories_reports_replay_field_when_implemented():
    NS = make_ns()

    @NS
    @Repository(Store)
    class ReplayableStoreLocations:
        def all(self):
            return []

        def data_view(self):
            return LocationView(fields=("lat", "lon"))

        def replay_field(self):
            return "id"  # arbitrary existing field, just to prove it's surfaced

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]

    assert schema["replay_field"] == "id"


def test_build_repositories_replay_field_is_none_without_opt_in():
    NS = make_ns()

    @NS
    @Repository(Store)
    class StoreLocationsNoReplay:
        def all(self):
            return []

        def data_view(self):
            return LocationView(fields=("lat", "lon"))

    with Context(namespaces={NS}) as ctx:
        schema = build_repositories(ctx)[0]

    assert schema["replay_field"] is None


# --- build_entity / coerce_key ----------------------------------------------


def test_build_entity_forces_key_value():
    entity = build_entity(Widget, {"name": "New"}, key="id", key_value=None)
    assert entity == Widget(id=None, name="New")


def test_build_entity_ignores_key_in_payload():
    entity = build_entity(Widget, {"id": "ignored", "name": "New"}, key="id", key_value=5)
    assert entity == Widget(id=5, name="New")


def test_coerce_key_unwraps_optional_int():
    assert coerce_key(Widget, "id", "42") == 42
