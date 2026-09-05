"""In-memory repository backing the table-view example."""

from opendataframework import Repository, Storage

from app.entities import Book


@Storage
@Repository(Book)
class Books:
    """In-memory ``Book`` repository.

    Implements no ``data_view()`` — the concept this example isolates is
    the implicit default table, not an override (see ../06-location-view
    for a repository that overrides it).
    """

    def __init__(self) -> None:
        """Start with an empty in-memory book list."""
        self._books: list[Book] = []
        self._next_id = 1

    def all(self) -> list[Book]:
        """Return every book."""
        return list(self._books)

    def save(self, book: Book) -> None:
        """Create or update a book.

        Args:
            book: The book to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
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

    def delete(self, book_id: int) -> None:
        """Delete the book matching ``book_id``, if one exists.

        Args:
            book_id: The ``id`` of the book to remove.
        """
        self._books = [b for b in self._books if b.id != book_id]
