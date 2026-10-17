import json
import urllib.request
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from opendataframework.context import Context
from opendataframework.entity import Entity
from opendataframework.namespace import Namespace
from opendataframework.repository import Repository
from opendataframework.view import ContentMetadata, DocumentView

from odf.ui import notebooks
from odf.ui.server import UiServer

pytestmark = pytest.mark.skipif(not notebooks.available(), reason="needs the notebook package")


@Entity(name="notebook-note")
@dataclass
class Note:
    id: int
    body: bytes | str


def notebook_bytes(source: str) -> bytes:
    import nbformat

    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])
    return nbformat.writes(nb).encode()


def notes_namespace(notes: dict[int, Note], names: dict[int, str]):
    """A namespace holding a writable ``Notes`` repository with a ``DocumentView``."""

    class NS(Namespace): ...

    @NS
    @Repository(Note)
    class Notes:
        def all(self):
            return list(notes.values())

        def save(self, note):
            notes[note.id] = note

        def delete(self, key):
            notes.pop(key)

        def data_view(self):
            return DocumentView(field="body")

        def content_metadata(self, note):
            return ContentMetadata(filename=names.get(note.id))

    return NS


@pytest.fixture
def contents():
    """A ``RepositoryContentsManager`` over a UI served by a ``TestClient``, and its notes."""
    from odf.ui.notebook_contents import RepositoryContentsManager

    notes = {
        1: Note(1, notebook_bytes("1 + 1")),
        2: Note(2, notebook_bytes("2 + 2")),
        3: Note(3, b"plain text"),
        4: Note(4, "inline"),
    }
    NS = notes_namespace(notes, {1: "analysis.ipynb", 3: "readme.txt"})
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj")._app)
        manager = RepositoryContentsManager(ui_url="")

        def request(method, url, body=None):
            from tornado.web import HTTPError

            response = client.request(method, url, content=body)
            if response.status_code >= 400:
                raise HTTPError(response.status_code, response.text)
            return response.content

        manager._request = request
        yield manager, notes


def test_contents_lists_document_repositories_and_their_notebook_records(contents):
    manager, _ = contents

    root = manager.get("")
    repo = manager.get("notes")
    record = manager.get("notes/1")

    assert [c["path"] for c in root["content"]] == ["notes"]
    # Only declared notebooks are listed; an undeclared one is still served.
    assert [c["path"] for c in repo["content"]] == ["notes/1"]
    assert [(c["path"], c["type"]) for c in record["content"]] == [
        ("notes/1/analysis.ipynb", "notebook")
    ]
    assert manager.file_exists("notes/2/2.ipynb")


def test_contents_reads_a_notebook_record_under_its_declared_name(contents):
    manager, _ = contents

    model = manager.get("notes/1/analysis.ipynb")

    assert model["type"] == "notebook"
    assert model["name"] == "analysis.ipynb"
    assert model["content"].cells[0].source == "1 + 1"
    assert not manager.file_exists("notes/1/1.ipynb")
    assert not manager.file_exists("notes/9/9.ipynb")


def test_contents_saves_a_notebook_into_its_record(contents):
    import nbformat

    manager, notes = contents
    model = manager.get("notes/1/analysis.ipynb")
    model["content"].cells[0].source = "3 + 3"

    saved = manager.save(
        {"type": "notebook", "content": model["content"]}, "notes/1/analysis.ipynb"
    )

    assert saved["path"] == "notes/1/analysis.ipynb"
    assert nbformat.reads(notes[1].body.decode(), 4).cells[0].source == "3 + 3"
    assert manager.list_checkpoints("notes/1/analysis.ipynb")


def test_contents_keeps_last_modified_until_the_notebook_changes(contents):
    manager, notes = contents
    first = manager.get("notes/2/2.ipynb", content=False)["last_modified"]
    again = manager.get("notes/2/2.ipynb", content=False)["last_modified"]
    notes[2] = Note(2, notebook_bytes("changed elsewhere"))
    changed = manager.get("notes/2/2.ipynb", content=False)["last_modified"]

    assert again == first
    assert changed > first


def test_contents_refuses_what_is_not_editing_a_notebook(contents):
    from tornado.web import HTTPError

    manager, _ = contents

    with pytest.raises(HTTPError) as not_a_notebook:
        manager.get("notes/3/3.ipynb")
    with pytest.raises(HTTPError) as other_path:
        manager.save({"type": "notebook", "content": {}}, "notes/1/copy.ipynb")
    with pytest.raises(HTTPError) as delete:
        manager.delete_file("notes/1/analysis.ipynb")
    with pytest.raises(HTTPError) as create:
        manager.new_untitled("notes/1")

    assert not_a_notebook.value.status_code == 400
    assert other_path.value.status_code == 404
    assert delete.value.status_code == 403
    assert create.value.status_code == 403


@pytest.mark.timeout(120)
def test_notebook_server_serves_records_from_a_running_ui(tmp_path):
    notes = {1: Note(1, notebook_bytes("1 + 1"))}
    NS = notes_namespace(notes, {1: "analysis.ipynb"})
    with Context(namespaces={NS}) as ctx:
        ui = UiServer(ctx, "proj", port=18778, notebooks=True)
        ui.start()
        try:
            port = ui._notebooks.start()
            again = ui._notebooks.start()
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/contents/notes/1/analysis.ipynb",
                headers={"Authorization": f"token {ui._notebooks.token}"},
            )
            with urllib.request.urlopen(request, timeout=10) as res:
                model = json.load(res)
        finally:
            ui.stop()

    assert again == port
    assert model["content"]["cells"][0]["source"] == "1 + 1"
    assert ui._notebooks._process is None
