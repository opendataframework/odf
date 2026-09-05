"""Registers this example's ``@Entity``/``@Repository``/``@Component`` classes for
``Server.from_config()`` to discover."""

from app import entities, repositories, storages

__all__ = [
    "entities",
    "repositories",
    "storages",
]
