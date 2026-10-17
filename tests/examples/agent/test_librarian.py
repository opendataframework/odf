from app.agents import Librarian
from app.repositories import Books
from opendataframework.agent import AgentProtocol

# Deliberately builds Books/Librarian directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/table_view/test_books.py.


def test_librarian_returns_an_authors_books_oldest_first():
    librarian = Librarian(Books())

    result = librarian.invoke("Anything by Le Guin?")

    assert [book["title"] for book in result] == [
        "A Wizard of Earthsea",
        "The Left Hand of Darkness",
    ]


def test_librarian_ranks_the_best_match_first_and_honours_limit():
    librarian = Librarian(Books())

    result = librarian.invoke("Children of Dune by Herbert", limit=1)

    assert result == [{"title": "Children of Dune", "author": "Frank Herbert", "year": 1976}]


def test_librarian_returns_nothing_when_no_book_matches():
    librarian = Librarian(Books())

    assert librarian.invoke("What about whales?") == []


def test_librarian_implements_agent_protocol():
    assert isinstance(Librarian(Books()), AgentProtocol)
