"""Registers this example's ``@Entity``/``@Repository`` classes for ``Server.from_config()`` to
discover."""

from app import entities, repositories

__all__ = [
    "entities",
    "repositories",
]
