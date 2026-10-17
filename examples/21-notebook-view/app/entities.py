"""Entities for the notebook-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Notebook:
    """A Jupyter notebook shown via ``Notebooks.data_view()``.

    Attributes:
        name: Primary key, the notebook's file name without ``.ipynb``.
        content: The notebook file's bytes.
    """

    name: str
    content: bytes
