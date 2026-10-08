import json

import pytest

from odf.ui import annotations


def box(label="parcel", x=10, y=20, width=30, height=40):
    return {"type": "box", "label": label, "x": x, "y": y, "width": width, "height": height}


def test_load_returns_empty_document_when_file_missing(tmp_path):
    assert annotations.load(tmp_path / "annotations.json") == {"version": 1, "repositories": {}}


def test_load_raises_on_invalid_json(tmp_path):
    path = tmp_path / "annotations.json"
    path.write_text("not json")

    with pytest.raises(ValueError, match="not valid JSON"):
        annotations.load(path)


def test_load_raises_when_json_is_not_an_object(tmp_path):
    path = tmp_path / "annotations.json"
    path.write_text("[1, 2, 3]")

    with pytest.raises(ValueError, match="JSON object"):
        annotations.load(path)


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "nested" / "dir" / "annotations.json"
    data = annotations.load(path)
    annotations.set_record(data, "photos", "a", 100, 200, [box()])

    annotations.save(path, data)

    assert annotations.load(path) == data
    assert json.loads(path.read_text()) == {
        "version": 1,
        "repositories": {
            "photos": {
                "labels": ["parcel"],
                "records": {"a": {"width": 100, "height": 200, "annotations": [box()]}},
            }
        },
    }
    assert list(path.parent.iterdir()) == [path]  # no temp file left behind


def test_repository_returns_empty_block_for_unknown_repository():
    assert annotations.repository({}, "photos") == {"labels": [], "records": {}}


def test_set_record_appends_new_labels_in_first_seen_order():
    data = {}

    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel"), box("door")])
    block = annotations.set_record(data, "photos", "b", 100, 100, [box("door"), box("cat")])

    assert block["labels"] == ["parcel", "door", "cat"]
    assert set(block["records"]) == {"a", "b"}


def test_set_record_keeps_repositories_separate():
    data = {}

    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel")])
    annotations.set_record(data, "scans", "a", 100, 100, [box("stamp")])

    assert annotations.repository(data, "photos")["labels"] == ["parcel"]
    assert annotations.repository(data, "scans")["labels"] == ["stamp"]


def test_set_record_with_no_annotations_removes_the_record_and_its_labels():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel")])

    block = annotations.set_record(data, "photos", "a", 100, 100, [])

    assert block == {"labels": [], "records": {}}


def test_set_record_keeps_a_label_another_record_still_uses():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel")])
    annotations.set_record(data, "photos", "b", 100, 100, [box("parcel")])

    block = annotations.set_record(data, "photos", "a", 100, 100, [])

    assert block["labels"] == ["parcel"]


def test_set_record_drops_a_label_its_only_box_was_relabelled_from():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box("parcle"), box("door")])

    block = annotations.set_record(data, "photos", "a", 100, 100, [box("parcel"), box("door")])

    assert block["labels"] == ["door", "parcel"]


def test_set_record_keeps_the_order_of_the_labels_still_used():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel"), box("door")])
    annotations.set_record(data, "photos", "b", 100, 100, [box("cat")])

    block = annotations.set_record(data, "photos", "a", 100, 100, [box("door")])

    assert block["labels"] == ["door", "cat"]


def test_set_record_drops_unused_labels_already_in_the_file():
    data = {"repositories": {"photos": {"labels": ["box", "door"], "records": {}}}}

    block = annotations.set_record(data, "photos", "a", 100, 100, [box("door")])

    assert block["labels"] == ["door"]


def test_set_record_strips_labels_and_rounds_coordinates():
    block = annotations.set_record(
        {}, "photos", "a", 100.4, 100, [box("  parcel ", x=1.6, y=2.2, width=10.5, height=3.4)]
    )

    assert block["records"]["a"] == {
        "width": 100,
        "height": 100,
        "annotations": [box("parcel", x=2, y=2, width=10, height=3)],
    }


def test_set_record_clamps_boxes_to_the_image():
    block = annotations.set_record(
        {}, "photos", "a", 100, 50, [box(x=-10, y=40, width=200, height=30)]
    )

    assert block["records"]["a"]["annotations"] == [box(x=0, y=40, width=100, height=10)]


@pytest.mark.parametrize(
    ("width", "height", "items"),
    [
        (0, 100, [box()]),
        ("100", 100, [box()]),
        (True, 100, [box()]),
        (100, 100, "nope"),
        (100, 100, ["nope"]),
        (100, 100, [{**box(), "type": "polygon"}]),
        (100, 100, [box(label="   ")]),
        (100, 100, [{**box(), "label": 3}]),
        (100, 100, [{**box(), "x": "1"}]),
        (100, 100, [box(width=0)]),
        (100, 100, [box(x=150)]),
    ],
)
def test_set_record_rejects_malformed_input(width, height, items):
    data = {}

    with pytest.raises(ValueError):
        annotations.set_record(data, "photos", "a", width, height, items)

    assert annotations.repository(data, "photos") == {"labels": [], "records": {}}


def span(label="total", start=7, end=14, text="$100.00"):
    return {"type": "span", "label": label, "start": start, "end": end, "text": text}


def page_box(label="logo", page=1, x=40, y=32.5, width=120, height=48):
    return {
        "type": "box",
        "label": label,
        "page": page,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "page_width": 612,
        "page_height": 792,
    }


def test_set_document_record_stores_spans_and_page_boxes_without_a_size():
    block = annotations.set_document_record({}, "papers", "a", [page_box(), span()])

    assert block == {
        "labels": ["total", "logo"],
        "records": {"a": {"annotations": [span(), page_box()]}},
    }


def test_set_document_record_keeps_spans_in_text_order():
    first = span("order", start=0, end=5, text="Order")
    block = annotations.set_document_record({}, "papers", "a", [span(), first])

    assert block["records"]["a"]["annotations"] == [first, span()]
    assert block["labels"] == ["order", "total"]


def test_set_document_record_strips_labels_and_counts_code_points():
    block = annotations.set_document_record(
        {}, "papers", "a", [span("  mood ", start=0, end=2, text="\U0001f600!")]
    )

    assert block["records"]["a"]["annotations"] == [
        span("mood", start=0, end=2, text="\U0001f600!")
    ]


def test_set_document_record_allows_spans_that_touch():
    items = [span("a", start=0, end=3, text="abc"), span("b", start=3, end=6, text="def")]

    block = annotations.set_document_record({}, "papers", "a", items)

    assert block["records"]["a"]["annotations"] == items


def test_set_document_record_clamps_page_boxes_and_rounds_to_hundredths():
    block = annotations.set_document_record(
        {}, "papers", "a", [page_box(x=-10, y=700.123, width=1000, height=200)]
    )

    assert block["records"]["a"]["annotations"] == [
        page_box(x=0, y=700.12, width=612, height=91.88)
    ]


def test_set_document_record_with_no_annotations_removes_the_record_and_its_labels():
    data = {}
    annotations.set_document_record(data, "papers", "a", [span()])
    annotations.set_document_record(data, "papers", "b", [page_box()])

    block = annotations.set_document_record(data, "papers", "a", [])

    assert block == {"labels": ["logo"], "records": {"b": {"annotations": [page_box()]}}}


@pytest.mark.parametrize(
    "items",
    [
        "nope",
        ["nope"],
        [{**span(), "type": "polygon"}],
        [span(label="   ")],
        [span(start=-1, end=6)],
        [span(start=7, end=7, text="")],
        [span(start=7.0)],
        [span(start=True, end=8, text="$100.00")],
        [span(text="$100")],
        [{**span(), "text": 7}],
        [span(), span("tax", start=10, end=16, text="0.00 +")],
        [page_box(page=0)],
        [page_box(page=1.5)],
        [page_box(width=0)],
        [page_box(x=700)],
        [{**page_box(), "page_width": 0}],
        [{**page_box(), "page_height": "792"}],
    ],
)
def test_set_document_record_rejects_malformed_input(items):
    data = {}

    with pytest.raises(ValueError):
        annotations.set_document_record(data, "papers", "a", items)

    assert annotations.repository(data, "papers") == {"labels": [], "records": {}}


def time_range(label="promo", start=100.0, end=200.5):
    return {"type": "range", "label": label, "start": start, "end": end}


def point(label="outlier", at=150.25, key="2"):
    return {"type": "point", "label": label, "at": at, "key": key}


def test_series_returns_empty_block_for_unknown_repository():
    assert annotations.series({}, "orders") == {"labels": [], "annotations": []}


def test_set_series_stores_ranges_and_points_in_time_order():
    early = point("spike", at=50, key="1")
    block = annotations.set_series({}, "orders", [point(), time_range(), early])

    assert block == {
        "labels": ["outlier", "promo", "spike"],
        "annotations": [early, time_range(), point()],
    }


def test_set_series_allows_ranges_that_overlap():
    items = [time_range(), time_range("sale", start=150, end=300)]

    block = annotations.set_series({}, "orders", items)

    assert block["annotations"] == items


def test_set_series_strips_labels():
    block = annotations.set_series({}, "orders", [time_range("  promo ")])

    assert block == {"labels": ["promo"], "annotations": [time_range()]}


def test_set_series_drops_labels_no_annotation_uses_any_more():
    data = {}
    annotations.set_series(data, "orders", [time_range(), point()])

    block = annotations.set_series(data, "orders", [point()])

    assert block == {"labels": ["outlier"], "annotations": [point()]}
    assert annotations.set_series(data, "orders", []) == {"labels": [], "annotations": []}


def test_set_series_leaves_other_repositories_alone():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box()])

    annotations.set_series(data, "orders", [time_range()])

    assert annotations.repository(data, "photos") == {
        "labels": ["parcel"],
        "records": {"a": {"width": 100, "height": 100, "annotations": [box()]}},
    }


@pytest.mark.parametrize(
    "items",
    [
        "nope",
        ["nope"],
        [{**time_range(), "type": "box"}],
        [time_range(label="   ")],
        [time_range(start=200, end=100)],
        [time_range(start=100, end=100)],
        [time_range(start="100")],
        [time_range(end=float("inf"))],
        [time_range(start=float("nan"))],
        [point(at=None)],
        [point(at=True)],
        [point(key="")],
        [point(key=2)],
        [{"type": "point", "label": "outlier", "at": 150.25}],
    ],
)
def test_set_series_rejects_malformed_input(items):
    data = {}

    with pytest.raises(ValueError):
        annotations.set_series(data, "orders", items)

    assert annotations.series(data, "orders") == {"labels": [], "annotations": []}
