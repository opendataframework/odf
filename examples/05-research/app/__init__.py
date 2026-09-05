"""Registers this example's ``@Entity``/``@Repository``/``@Component``/``@Task`` classes for
``Server.from_config()`` to discover."""

from app import entities, experiments, repositories, storages

__all__ = [
    "entities",
    "experiments",
    "repositories",
    "storages",
]
