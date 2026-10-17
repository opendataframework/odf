"""Jupyter contents backed by a UI's document records.

Loaded only inside the Jupyter subprocess ``odf.ui.notebooks.NotebookServer``
launches, which names ``RepositoryContentsManager`` as its contents manager;
this is the one module in ``odf`` that imports Jupyter.

Each notebook record is a file in a directory of its own, so it keeps the
name its repository declares for it::

    <repository>/                    a DocumentView repository
    <repository>/<key>/              one of its records
    <repository>/<key>/<name>.ipynb  that record's notebook

``<name>.ipynb`` is the ``content_metadata()`` file name, or ``<key>.ipynb``
without one. Reads and saves go through the UI's record media endpoints, and
so through the repository's ``save()``. Notebooks can't be created, renamed
or deleted here, only edited, since a record is more than its notebook.
"""

import copy
import hashlib
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import quote

import nbformat
from jupyter_server.services.contents.checkpoints import Checkpoints, GenericCheckpointsMixin
from jupyter_server.services.contents.manager import ContentsManager
from tornado.web import HTTPError
from traitlets import Unicode, default

_NOTEBOOK_TYPE = "application/x-ipynb+json"

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def is_notebook(content: dict | None) -> bool:
    """Whether a record's declared content (its ``"$content"``) is a notebook."""
    if not content:
        return False
    return (content.get("filename") or "").lower().endswith(".ipynb") or (
        (content.get("content_type") or "").partition(";")[0].strip() == _NOTEBOOK_TYPE
    )


def _name(key: str, content: dict | None) -> str:
    """The file name a record's notebook is shown under."""
    filename = (content or {}).get("filename") or ""
    return filename if filename.lower().endswith(".ipynb") else f"{key}.ipynb"


class RepositoryCheckpoints(GenericCheckpointsMixin, Checkpoints):
    """One checkpoint per notebook, held in memory while Jupyter runs."""

    def __init__(self, **kwargs) -> None:
        """Start with no checkpoints."""
        super().__init__(**kwargs)
        self._saved: dict[str, tuple[dict, datetime]] = {}

    def create_notebook_checkpoint(self, nb, path):
        """Keep a copy of ``nb`` as ``path``'s checkpoint."""
        self._saved[path] = (copy.deepcopy(nb), datetime.now(UTC))
        return self._model(path)

    def create_file_checkpoint(self, content, format, path):
        """Refuse: only notebooks are served here."""
        raise HTTPError(400, "Only notebooks have checkpoints")

    def get_notebook_checkpoint(self, checkpoint_id, path):
        """Return the notebook kept as ``path``'s checkpoint."""
        if path not in self._saved:
            raise HTTPError(404, f"No checkpoint for {path}")
        return {"type": "notebook", "content": copy.deepcopy(self._saved[path][0])}

    def get_file_checkpoint(self, checkpoint_id, path):
        """Refuse: only notebooks are served here."""
        raise HTTPError(404, f"No checkpoint for {path}")

    def list_checkpoints(self, path):
        """Return ``path``'s checkpoint, if it has one."""
        return [self._model(path)] if path in self._saved else []

    def delete_checkpoint(self, checkpoint_id, path):
        """Drop ``path``'s checkpoint."""
        self._saved.pop(path, None)

    def rename_checkpoint(self, checkpoint_id, old_path, new_path):
        """Move ``old_path``'s checkpoint to ``new_path``."""
        if old_path in self._saved:
            self._saved[new_path] = self._saved.pop(old_path)

    def _model(self, path: str) -> dict:
        return {"id": "checkpoint", "last_modified": self._saved[path][1]}


class RepositoryContentsManager(ContentsManager):
    """Serves a UI's notebook records as Jupyter contents (see the module docstring)."""

    ui_url = Unicode(help="Base URL of the UI whose records are served.", config=True)

    @default("checkpoints_class")
    def _default_checkpoints_class(self):
        return RepositoryCheckpoints

    def __init__(self, **kwargs) -> None:
        """Start with no notebook seen yet."""
        super().__init__(**kwargs)
        # Path → (hash of its bytes, when they were first seen). Jupyter warns
        # of a conflicting change on save when a notebook's last_modified moves
        # under it, so it only moves when the content does.
        self._seen: dict[str, tuple[str, datetime]] = {}

    # --- odf's HTTP API ---

    def _request(self, method: str, url: str, body: bytes | None = None) -> bytes:
        """Call the UI, turning its error responses into Jupyter's."""
        request = urllib.request.Request(self.ui_url + url, data=body, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
                return response.read()
        except urllib.error.HTTPError as exc:
            raise HTTPError(exc.code, exc.read().decode(errors="replace")) from exc
        except urllib.error.URLError as exc:
            raise HTTPError(502, f"odf UI unreachable: {exc.reason}") from exc

    def _repositories(self) -> dict[str, dict]:
        """The UI's document repositories, by name."""
        schemas = json.loads(self._request("GET", "/api/repositories"))
        return {
            s["name"]: s
            for s in schemas
            if s["readable"] and (s.get("view") or {}).get("kind") == "document"
        }

    def _records(self, repo: str) -> dict[str, dict]:
        """A document repository's records, by key."""
        schema = self._repositories().get(repo)
        if schema is None:
            raise HTTPError(404, f"No document repository {repo!r}")
        records = json.loads(self._request("GET", f"/api/repositories/{quote(repo)}/records"))
        return {str(r[schema["key"]]): r for r in records}

    def _record(self, repo: str, key: str) -> dict | None:
        """One record of a document repository, or ``None``."""
        return self._records(repo).get(key)

    def _media_url(self, repo: str, key: str) -> str:
        return f"/api/repositories/{quote(repo)}/records/{quote(key, safe='')}/media"

    # --- paths ---

    def _split(self, path: str) -> list[str]:
        return [part for part in path.strip("/").split("/") if part]

    def _notebook(self, path: str) -> tuple[str, str]:
        """Resolve a notebook's path to its (repository, key), or raise 404."""
        parts = self._split(path)
        if len(parts) == 3:
            repo, key, name = parts
            record = self._record(repo, key)
            if record is not None and name == _name(key, record.get("$content")):
                return repo, key
        raise HTTPError(404, f"No notebook at {path}")

    def dir_exists(self, path):
        """Whether ``path`` is the root, a document repository or one of its records."""
        parts = self._split(path)
        if not parts:
            return True
        if len(parts) == 1:
            return parts[0] in self._repositories()
        if len(parts) == 2:
            return parts[0] in self._repositories() and self._record(*parts) is not None
        return False

    def file_exists(self, path):
        """Whether ``path`` is a record's notebook."""
        try:
            self._notebook(path)
        except HTTPError:
            return False
        return True

    def is_hidden(self, path):
        """Nothing served here is hidden."""
        return False

    # --- models ---

    def _base(self, path: str, type_: str, last_modified: datetime = _EPOCH) -> dict:
        path = path.strip("/")
        return {
            "name": path.rsplit("/", 1)[-1],
            "path": path,
            "type": type_,
            "created": last_modified,
            "last_modified": last_modified,
            "content": None,
            "format": None,
            "mimetype": None,
            "size": None,
            "writable": type_ == "notebook",
            "hash": None,
            "hash_algorithm": None,
        }

    def _dir_model(self, path: str, content: bool) -> dict:
        model = self._base(path, "directory")
        if not content:
            return model
        parts = self._split(path)
        prefix = "/".join(parts)
        if not parts:
            children = [self._base(name, "directory") for name in self._repositories()]
        elif len(parts) == 1:
            children = [
                self._base(f"{prefix}/{key}", "directory")
                for key, record in self._records(parts[0]).items()
                if is_notebook(record.get("$content"))
            ]
        else:
            record = self._record(*parts)
            name = _name(parts[1], record.get("$content"))
            children = [self._base(f"{prefix}/{name}", "notebook")]
        model["content"] = children
        model["format"] = "json"
        return model

    def _notebook_model(self, path: str, content: bool, require_hash: bool) -> dict:
        repo, key = self._notebook(path)
        raw = self._request("GET", self._media_url(repo, key))
        digest = hashlib.sha256(raw).hexdigest()
        seen = self._seen.get(path)
        if seen is None or seen[0] != digest:
            seen = self._seen[path] = (digest, datetime.now(UTC))
        model = self._base(path, "notebook", seen[1])
        model["size"] = len(raw)
        if content:
            validation_error: dict = {}
            try:
                nb = nbformat.reads(
                    raw.decode("utf-8"), as_version=4, capture_validation_error=validation_error
                )
            except Exception as exc:
                raise HTTPError(400, f"{path} is not a notebook: {exc}") from exc
            self.mark_trusted_cells(nb, path)
            model["content"] = nb
            model["format"] = "json"
            self.validate_notebook_model(model, validation_error)
        if require_hash:
            model["hash"] = digest
            model["hash_algorithm"] = "sha256"
        return model

    def get(self, path, content=True, type=None, format=None, require_hash=False):
        """Return the model of a directory or a notebook."""
        if self.dir_exists(path):
            if type not in (None, "directory"):
                raise HTTPError(400, f"{path} is a directory, not a {type}")
            return self._dir_model(path, content)
        if type not in (None, "notebook"):
            raise HTTPError(400, f"{path} is a notebook, not a {type}")
        return self._notebook_model(path, content, require_hash)

    def save(self, model, path):
        """Save a notebook into its record, through the repository's ``save()``."""
        path = path.strip("/")
        if model.get("type") != "notebook" or "content" not in model:
            raise HTTPError(400, "Only notebooks can be saved here")
        repo, key = self._notebook(path)
        self.run_pre_save_hooks(model=model, path=path)
        nb = nbformat.from_dict(model["content"])
        self.check_and_sign(nb, path)
        raw = nbformat.writes(nb).encode("utf-8")
        self._request("PUT", self._media_url(repo, key), raw)
        self._seen[path] = (hashlib.sha256(raw).hexdigest(), datetime.now(UTC))
        if not self.checkpoints.list_checkpoints(path):
            self.create_checkpoint(path)
        saved = self.get(path, content=False)
        self.emit(data={"action": "save", "path": path})
        return saved

    def delete_file(self, path):
        """Refuse: a record is more than its notebook."""
        raise HTTPError(403, "Notebooks are deleted with their record, in the odf UI")

    def rename_file(self, old_path, new_path):
        """Refuse: a notebook's name is its repository's to declare."""
        raise HTTPError(403, "Notebooks can't be renamed here")

    def new_untitled(self, path="", type="", ext=""):
        """Refuse: a notebook is a record's, and records are added in the odf UI."""
        raise HTTPError(403, "Notebooks are added as records, in the odf UI")

    def info_string(self):
        """The line Jupyter logs about where its contents come from."""
        return f"Serving notebook records from {self.ui_url}"
