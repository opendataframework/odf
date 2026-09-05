from odf.ui import layout


def test_load_returns_empty_dict_when_file_missing(tmp_path):
    assert layout.load(tmp_path / "layout.json") == {}


def test_load_returns_empty_dict_on_invalid_json(tmp_path):
    path = tmp_path / "layout.json"
    path.write_text("not json")

    assert layout.load(path) == {}


def test_load_returns_empty_dict_when_json_is_not_an_object(tmp_path):
    path = tmp_path / "layout.json"
    path.write_text("[1, 2, 3]")

    assert layout.load(path) == {}


def test_save_then_load_round_trips(tmp_path):
    positions = {"users": {"col": 2, "row": 1}, "postgres": {"col": 0, "row": 0}}
    path = tmp_path / "layout.json"

    layout.save(path, positions)

    assert layout.load(path) == positions


def test_save_then_load_round_trips_with_icon_override(tmp_path):
    positions = {
        "users": {"col": 2, "row": 1, "icon": "gateway"},
        "postgres": {"col": 0, "row": 0},
    }
    path = tmp_path / "layout.json"

    layout.save(path, positions)

    assert layout.load(path) == positions


def test_save_then_load_round_trips_with_color_override(tmp_path):
    positions = {
        "users": {"col": 2, "row": 1, "color": "#4f8ef0"},
        "postgres": {"col": 0, "row": 0},
    }
    path = tmp_path / "layout.json"

    layout.save(path, positions)

    assert layout.load(path) == positions


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "layout.json"
    layout.save(path, {"a": {"col": 1, "row": 1}})

    assert layout.load(path) == {"a": {"col": 1, "row": 1}}


def test_save_overwrites_existing_file(tmp_path):
    path = tmp_path / "layout.json"
    layout.save(path, {"a": {"col": 1, "row": 1}})
    layout.save(path, {"b": {"col": 2, "row": 2}})

    assert layout.load(path) == {"b": {"col": 2, "row": 2}}
