import pytest

from odf.ui import layout, views
from odf.ui.topology import TopologyView


def test_no_views_declared():
    assert views.from_config({}) == ({}, None)
    assert views.from_config({"views": {}}) == ({}, None)


def test_views_keep_their_order_and_the_first_is_the_default():
    found, default = views.from_config(
        {"views": {"manager": {"label": "Bakery"}, "system": {}, "other": {}}}
    )

    assert list(found) == ["manager", "system", "other"]
    assert default == "manager"
    assert found["manager"].label == "Bakery"
    assert found["system"].label == "system"
    assert found["system"].topology == TopologyView()


def test_default_true_picks_the_default():
    _, default = views.from_config({"views": {"a": {}, "b": {"default": True}}})

    assert default == "b"


def test_a_views_topology_table_is_read_as_ui_topology_is():
    found, _ = views.from_config(
        {"views": {"manager": {"topology": {"config": False, "tasks": ["ImportSheets"]}}}}
    )

    assert found["manager"].topology == TopologyView(
        config=False, show={"task": frozenset({"import-sheets"})}
    )


@pytest.mark.parametrize(
    ("ui", "match"),
    [
        ({"views": ["manager"]}, r"\[ui\.views\] must be a table"),
        ({"views": {"a": "x"}}, r"\[ui\.views\.a\] must be a table"),
        ({"views": {"a": {"colour": 1}}}, r"Unknown \[ui\.views\.a\] key\(s\): colour"),
        ({"views": {"a": {"label": 1}}}, r"\[ui\.views\.a\] label must be text"),
        ({"views": {"a": {"default": "yes"}}}, r"\[ui\.views\.a\] default must be true or false"),
        ({"views": {"a": {"topology": []}}}, r"\[ui\.views\.a\.topology\] must be a table"),
        ({"views": {"a": {"topology": {"task": []}}}}, r"Unknown \[ui\.views\.a\.topology\]"),
        ({"views": {"a": {"default": True}, "b": {"default": True}}}, "More than one.*a, b"),
        ({"topology": {}, "views": {"a": {}}}, "both set"),
    ],
)
def test_invalid_views_are_rejected(ui, match):
    with pytest.raises(ValueError, match=match):
        views.from_config(ui)


def test_ui_topology_alone_is_left_to_topology_view():
    assert views.from_config({"topology": {"config": False}}) == ({}, None)


# --- each view's own places in layout.json -------------------------------------


def test_for_view_puts_the_views_places_over_the_top_level_ones():
    saved = {
        "task.a": {"col": 1, "row": 1, "icon": "truck"},
        "task.b": {"col": 2, "row": 2},
        "_grid": {"nw": 1, "ne": 0, "se": 0, "sw": 0},
        "_layers": {"cafe": "#f06595"},
        "_views": {
            "manager": {
                "task.a": {"col": 5, "row": 0},
                "task.c": {"col": 6, "row": 0},
                "_grid": {"nw": 0, "ne": 2, "se": 0, "sw": 0},
            },
        },
    }

    assert layout.for_view(saved, "manager") == {
        "task.a": {"col": 5, "row": 0, "icon": "truck"},
        "task.b": {"col": 2, "row": 2},
        "task.c": {"col": 6, "row": 0},
        "_grid": {"nw": 0, "ne": 2, "se": 0, "sw": 0},
        "_layers": {"cafe": "#f06595"},
    }


def test_for_view_without_places_of_its_own_is_the_top_level():
    saved = {"task.a": {"col": 1, "row": 1}, "_views": {"other": {"task.a": {"col": 9, "row": 9}}}}

    assert layout.for_view(saved, "manager") == {"task.a": {"col": 1, "row": 1}}
    assert layout.for_view({"_views": "junk", "task.a": {"col": 1, "row": 1}}, "m") == {
        "task.a": {"col": 1, "row": 1}
    }
