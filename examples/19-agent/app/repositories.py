"""In-memory repository backing the agent example."""

from opendataframework import Repository, Storage

from app.entities import Book

# (title, author, year)
_SEED_BOOKS: tuple[tuple[str, str, int], ...] = (
    ("Dune", "Frank Herbert", 1965),
    ("Children of Dune", "Frank Herbert", 1976),
    ("The Left Hand of Darkness", "Ursula K. Le Guin", 1969),
    ("A Wizard of Earthsea", "Ursula K. Le Guin", 1968),
    ("Neuromancer", "William Gibson", 1984),
    ("Foundation", "Isaac Asimov", 1951),
)


@Storage
@Repository(Book)
class Books:
    """In-memory ``Book`` repository, pre-seeded with ``_SEED_BOOKS``."""

    def __init__(self) -> None:
        """Seed the in-memory catalogue from ``_SEED_BOOKS``."""
        self._books: list[Book] = [
            Book(id=book_id, title=title, author=author, year=year)
            for book_id, (title, author, year) in enumerate(_SEED_BOOKS, start=1)
        ]
        self._next_id = len(self._books) + 1

    def all(self) -> list[Book]:
        """Return every book."""
        return list(self._books)

    def save(self, book: Book) -> None:
        """Create or update a book.

        Args:
            book: The book to persist. An unset ``id`` creates a new record
                and has one assigned; a set ``id`` updates the matching
                record in place.
        """
        if book.id is None:
            book.id = self._next_id
            self._next_id += 1
            self._books.append(book)
            return
        for i, existing in enumerate(self._books):
            if existing.id == book.id:
                self._books[i] = book
                return
