import json
import os
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


@pytest.fixture
def running_ui():
    """A served UI with notebook editing, its Jupyter started, and its notes."""
    notes = {1: Note(1, notebook_bytes("1 + 1"))}
    NS = notes_namespace(notes, {1: "analysis.ipynb"})
    with Context(namespaces={NS}) as ctx:
        ui = UiServer(ctx, "proj", port=18778, notebooks=True)
        ui.start()
        try:
            yield ui, notes
        finally:
            ui.stop()


def jupyter(ui, method, path, body=None, headers=None):
    """Request Jupyter's ``path`` through the UI, with its token, as JSON."""
    request = urllib.request.Request(
        f"{ui.local_url}/proxy/jupyter/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"token {ui._notebooks.token}", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=30) as res:
        return json.load(res)


@pytest.mark.timeout(120)
def test_notebook_server_serves_records_through_the_ui(running_ui):
    ui, _ = running_ui

    session = TestClient(ui._app).post("/api/notebooks/session").json()
    port = ui._notebooks.start()
    model = jupyter(ui, "GET", "api/contents/notes/1/analysis.ipynb")
    page = urllib.request.urlopen(
        f"{ui.local_url}/proxy/jupyter/notebooks/notes/1/analysis.ipynb?token={session['token']}",
        timeout=30,
    )

    assert session == {"url": "/proxy/jupyter/", "token": ui._notebooks.token}
    assert ui._notebooks.origin == f"http://127.0.0.1:{port}"
    assert model["content"]["cells"][0]["source"] == "1 + 1"
    assert page.status == 200
    assert "frame-ancestors 'self'" in page.headers["Content-Security-Policy"]
    ui.stop()
    assert ui._notebooks._process is None


@pytest.mark.timeout(120)
@pytest.mark.skipif(not hasattr(os, "getsid"), reason="POSIX sessions")
def test_notebook_server_shuts_down_on_its_own_not_on_the_terminal_s_ctrl_c(running_ui):
    ui, _ = running_ui
    ui._notebooks.start()
    process = ui._notebooks._process
    jupyter(ui, "POST", "api/kernels", {})
    request_shutdown = ui._notebooks._request_shutdown
    answers = []
    ui._notebooks._request_shutdown = lambda: answers.append(request_shutdown()) or answers[-1]

    separate = os.getsid(process.pid) != os.getsid(0)
    ui._notebooks.stop()

    # Out of the terminal's session, so Ctrl+C reaches only odf, and stopped
    # through Jupyter's shutdown request, not a signal.
    assert separate
    assert answers == [True]
    assert process.returncode is not None


@pytest.mark.timeout(120)
def test_notebook_server_only_listens_on_loopback(running_ui):
    import socket

    ui, _ = running_ui
    port = ui._notebooks.start()
    # The address this machine reaches the network from; nothing is sent.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))
        except OSError:
            pytest.skip("no network interface to try")
        outside = probe.getsockname()[0]
    if outside.startswith("127."):
        pytest.skip("no non-loopback address to try")

    with socket.socket() as sock:
        sock.settimeout(2)
        refused = sock.connect_ex((outside, port)) != 0

    assert refused


def browser_cookies(ui) -> str:
    """The ``Cookie`` header of a browser that opened Jupyter through the UI with its token."""
    import http.cookiejar

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(f"{ui.local_url}/proxy/jupyter/tree?token={ui._notebooks.token}", timeout=30)
    return "; ".join(f"{c.name}={c.value}" for c in jar)


def kernel_channels(ui, kernel_id, origin):
    """Connect to a kernel's channels through the UI, as a browser on ``origin`` would."""
    from tornado.httpclient import HTTPRequest
    from tornado.websocket import websocket_connect

    return websocket_connect(
        HTTPRequest(
            f"ws://127.0.0.1:18778/proxy/jupyter/api/kernels/{kernel_id}/channels",
            headers={"Cookie": browser_cookies(ui), "Origin": origin},
        )
    )


@pytest.mark.timeout(120)
def test_notebook_kernels_run_over_a_websocket_through_the_ui(running_ui):
    import asyncio
    import uuid

    ui, _ = running_ui
    ui._notebooks.start()
    kernel = jupyter(ui, "POST", "api/kernels", {})
    msg_id = uuid.uuid4().hex
    request = {
        "header": {
            "msg_id": msg_id,
            "msg_type": "kernel_info_request",
            "username": "test",
            "session": uuid.uuid4().hex,
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "content": {},
        "channel": "shell",
    }

    async def kernel_info():
        conn = await kernel_channels(ui, kernel["id"], "http://127.0.0.1:18778")
        await conn.write_message(json.dumps(request))
        while True:
            message = json.loads(await asyncio.wait_for(conn.read_message(), 60))
            if message["msg_type"] == "kernel_info_reply":
                conn.close()
                return message

    reply = asyncio.run(kernel_info())

    assert reply["parent_header"]["msg_id"] == msg_id
    assert reply["content"]["status"] == "ok"


@pytest.mark.timeout(120)
def test_notebook_server_refuses_another_site_through_the_ui(running_ui):
    import asyncio
    import urllib.error

    from tornado.httpclient import HTTPClientError

    ui, _ = running_ui
    ui._notebooks.start()
    kernel = jupyter(ui, "POST", "api/kernels", {})
    elsewhere = "https://elsewhere.example"
    request = urllib.request.Request(
        f"{ui.local_url}/proxy/jupyter/api/kernels",
        data=b"{}",
        method="POST",
        headers={"Cookie": browser_cookies(ui), "Origin": elsewhere},
    )

    with pytest.raises(urllib.error.HTTPError) as http:
        urllib.request.urlopen(request, timeout=30)

    async def connect():
        await kernel_channels(ui, kernel["id"], elsewhere)

    with pytest.raises(HTTPClientError) as websocket:
        asyncio.run(connect())

    assert http.value.code in (403, 404)
    assert websocket.value.code == 403


def test_jupyter_is_unavailable_through_the_ui_until_it_starts():
    NS = notes_namespace({}, {})
    with Context(namespaces={NS}) as ctx:
        client = TestClient(UiServer(ctx, "proj", notebooks=True)._app)

        response = client.get("/proxy/jupyter/api/status")

    assert response.status_code == 503


@pytest.mark.parametrize("curve", [True, False])
def test_notebook_server_encrypts_kernel_traffic_when_pyzmq_can(monkeypatch, tmp_path, curve):
    import zmq

    monkeypatch.setattr(zmq, "has", lambda capability: curve)

    config = notebooks.NotebookServer("", "/proxy/jupyter/", tmp_path)._config()

    if curve:
        assert config["KernelManager"] == {"transport_encryption": "auto"}
    else:
        assert "KernelManager" not in config
