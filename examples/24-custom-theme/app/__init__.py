"""Registers this example's ``@Entity``/``@Repository``/``@Task`` classes for
``Server.from_config()`` to discover."""

from app import entities, repositories, tasks

__all__ = [
    "entities",
    "repositories",
    "tasks",
]
