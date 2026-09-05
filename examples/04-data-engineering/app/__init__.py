"""Registers this example's ``@Entity``/``@Repository``/``@Component``/``@Task``/``@Pipeline``
classes for ``Server.from_config()`` to discover."""

from app import entities, pipelines, repositories, storages, tasks

__all__ = [
    "entities",
    "pipelines",
    "repositories",
    "storages",
    "tasks",
]
