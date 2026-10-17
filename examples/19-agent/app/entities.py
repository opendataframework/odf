"""Entities for the agent example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class Book:
    """A book in the library's catalogue.

    Attributes:
        id: Primary key, ``None`` until ``Books.save()`` assigns one.
        title: The book's title.
        author: The book's author.
        year: The year it was first published.
    """

    id: int | None
    title: str
    author: str
    year: int
