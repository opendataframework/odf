"""File-backed repository behind the reverse-proxy example."""

from pathlib import Path

from opendataframework import ContentMetadata, DocumentView, Repository, Storage

from app.entities import Notebook

_NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent / "notebooks"


@Storage
@Repository(Notebook)
class Notebooks:
    """The ``.ipynb`` files in ``notebooks/``, one record per file.

    The same repository as ``21-notebook-view``'s, here so **Edit in Jupyter**
    can be tried through the proxy: Jupyter's pages and kernels go through
    the UI at ``/proxy/jupyter/``, behind the same login.

    Args:
        directory: Where the notebooks are kept. Defaults to this example's
            ``notebooks/``.
    """

    def __init__(self, directory: Path = _NOTEBOOKS_DIR) -> None:
        """Serve the notebooks in ``directory``."""
        self._dir = directory

    def all(self) -> list[Notebook]:
        """Return every notebook, by name."""
        return [
            Notebook(path.stem, path.read_bytes()) for path in sorted(self._dir.glob("*.ipynb"))
        ]

    def save(self, notebook: Notebook) -> None:
        """Write a notebook to its file, creating it if it is new.

        Args:
            notebook: The notebook to write.

        Raises:
            ValueError: If its name isn't a plain file name.
        """
        self._path(notebook.name).write_bytes(notebook.content)

    def delete(self, name: str) -> None:
        """Delete a notebook's file, if it exists.

        Args:
            name: The notebook's name.
        """
        self._path(name).unlink(missing_ok=True)

    def data_view(self) -> DocumentView:
        """Render notebooks as documents, in place of the default table."""
        return DocumentView(field="content")

    def content_metadata(self, notebook: Notebook) -> ContentMetadata:
        """Name each notebook's file and declare it a notebook.

        Args:
            notebook: The notebook to describe.

        Returns:
            The notebook's file name and type.
        """
        return ContentMetadata(
            filename=f"{notebook.name}.ipynb", content_type="application/x-ipynb+json"
        )

    def _path(self, name: str) -> Path:
        """The file a notebook named ``name`` is kept in."""
        if not name or Path(name).name != name or name.startswith("."):
            raise ValueError(f"Not a notebook name: {name!r}")
        return self._dir / f"{name}.ipynb"
