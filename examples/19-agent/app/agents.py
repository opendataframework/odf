"""Librarian agent for the agent example."""

import re

from opendataframework import Agent, Analytics

from app.repositories import Books

# Words too common to say anything about which book is meant.
_STOP_WORDS = frozenset(
    {"a", "an", "and", "any", "anything", "about", "by", "for", "is", "of", "the", "what", "who"}
)


@Analytics
@Agent
class Librarian:
    """Answers questions about the catalogue with the books that match best.

    ``invoke()`` takes the question as an argument, which is what makes this
    an agent rather than a task: the UI asks for it in a form, and the MCP
    server publishes it as the ``question`` parameter of
    ``agent.librarian.invoke``. ``Books`` is injected through the constructor, so
    the topology shows what the agent can read.
    """

    def __init__(self, books: Books) -> None:
        """Store the catalogue to search.

        Args:
            books: The repository the answers come from.
        """
        self.books = books

    def invoke(self, question: str, limit: int = 3) -> list[dict]:
        """Return the books whose title or author best match ``question``.

        This is where a real agent would hand ``question`` and the catalogue
        to a model, usually another injected component. Keyword matching
        keeps the example runnable offline.

        Args:
            question: The question, in plain words (``"Anything by Herbert?"``).
            limit: The most books to return.

        Returns:
            Up to ``limit`` ``{"title", "author", "year"}`` dicts, best match
            first. Empty if nothing matches.
        """
        words = set(re.findall(r"[a-z]+", question.lower())) - _STOP_WORDS
        scored = []
        for book in self.books.all():
            haystack = set(re.findall(r"[a-z]+", f"{book.title} {book.author}".lower()))
            score = len(words & haystack)
            if score:
                scored.append((score, book))
        scored.sort(key=lambda pair: (-pair[0], pair[1].year))
        return [
            {"title": book.title, "author": book.author, "year": book.year}
            for _, book in scored[:limit]
        ]
