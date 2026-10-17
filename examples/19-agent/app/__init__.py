"""Registers this example's ``@Entity``/``@Repository``/``@Agent`` classes for
``Server.from_config()`` to discover."""

from app import agents, entities, repositories

__all__ = [
    "agents",
    "entities",
    "repositories",
]
