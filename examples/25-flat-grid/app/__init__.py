"""Registers this example's ``@Entity``/``@Repository``/``@Service``/``@Task``/``@Pipeline``/
``@Function`` objects for ``Server.from_config()`` to discover."""

from app import entities, functions, pipelines, repositories, services, tasks

__all__ = [
    "entities",
    "functions",
    "pipelines",
    "repositories",
    "services",
    "tasks",
]
