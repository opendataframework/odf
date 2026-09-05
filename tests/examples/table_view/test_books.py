from app.entities import Book
from app.repositories import Books
from opendataframework.view import DataViewProtocol

# Deliberately builds Books directly rather than going through Project/
# Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_books_save_assigns_incrementing_ids():
    books = Books()

    books.save(Book(id=None, title="Dune", author="Frank Herbert"))
    books.save(Book(id=None, title="Foundation", author="Isaac Asimov"))

    assert [b.id for b in books.all()] == [1, 2]


def test_books_save_updates_existing_record():
    books = Books()
    books.save(Book(id=None, title="Dune", author="Frank Herbert"))
    saved = books.all()[0]

    saved.title = "Dune (revised)"
    books.save(saved)

    assert len(books.all()) == 1
    assert books.all()[0].title == "Dune (revised)"


def test_books_delete_removes_record():
    books = Books()
    books.save(Book(id=None, title="Dune", author="Frank Herbert"))

    books.delete(1)

    assert books.all() == []


def test_books_implements_no_data_view():
    books = Books()

    assert not isinstance(books, DataViewProtocol)
