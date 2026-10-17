import json
import shutil

import pytest
from app.entities import Notebook
from app.repositories import Notebooks
from opendataframework import DocumentView

from .conftest import EXAMPLE_DIR

# Deliberately builds Notebooks directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


@pytest.fixture
def notebooks(tmp_path):
    """``Notebooks`` over a copy of the example's notebooks, so saving leaves them alone."""
    shutil.copytree(EXAMPLE_DIR / "notebooks", tmp_path, dirs_exist_ok=True)
    return Notebooks(tmp_path)


def test_notebooks_are_the_example_s_ipynb_files(notebooks):
    records = notebooks.all()

    assert [n.name for n in records] == ["sales-summary", "scratch"]
    for notebook in records:
        assert json.loads(notebook.content)["nbformat"] == 4


def test_notebooks_declare_each_file_a_notebook(notebooks):
    metadata = notebooks.content_metadata(notebooks.all()[0])

    assert metadata.filename == "sales-summary.ipynb"
    assert metadata.content_type == "application/x-ipynb+json"
    assert notebooks.data_view() == DocumentView(field="content")


def test_notebooks_save_writes_the_file(notebooks, tmp_path):
    notebooks.save(Notebook("scratch", b'{"cells": []}'))
    notebooks.delete("sales-summary")

    assert (tmp_path / "scratch.ipynb").read_bytes() == b'{"cells": []}'
    assert [n.name for n in notebooks.all()] == ["scratch"]


@pytest.mark.parametrize("name", ["", "../escape", "sub/dir", ".hidden"])
def test_notebooks_refuse_a_name_that_is_not_a_plain_file_name(notebooks, name):
    with pytest.raises(ValueError, match="Not a notebook name"):
        notebooks.save(Notebook(name, b"{}"))
