"""Registers this example's ``@Entity``/``@Repository``/``@Component`` classes for
``Server.from_config()`` to discover."""

from app import components, entities, repositories

__all__ = [
    "components",
    "entities",
    "repositories",
]
