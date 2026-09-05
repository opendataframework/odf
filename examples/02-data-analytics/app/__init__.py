"""Registers this example's ``@Entity``/``@Repository``/``@Component``/``@Task`` classes for
``Server.from_config()`` to discover."""

from app import analytics, entities, repositories, storages

__all__ = [
    "analytics",
    "entities",
    "repositories",
    "storages",
]
