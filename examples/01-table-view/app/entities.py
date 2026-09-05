"""Entities for the table-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Book:
    """A book tracked in the library's catalog.

    Attributes:
        id: Primary key, ``None`` until ``Books.save()`` assigns one.
        title: The book's title.
        author: The book's author.
    """

    id: int | None
    title: str
    author: str
