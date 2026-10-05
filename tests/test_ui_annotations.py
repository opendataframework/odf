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


def test_set_record_with_no_annotations_removes_the_record_but_keeps_labels():
    data = {}
    annotations.set_record(data, "photos", "a", 100, 100, [box("parcel")])

    block = annotations.set_record(data, "photos", "a", 100, 100, [])

    assert block == {"labels": ["parcel"], "records": {}}


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
