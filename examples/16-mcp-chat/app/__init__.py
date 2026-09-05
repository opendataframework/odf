"""Registers this example's ``@Entity``/``@Repository``/``@Service``/``@Task`` classes for
``Server.from_config()`` to discover."""

from app import entities, repositories, services, tasks

__all__ = [
    "entities",
    "repositories",
    "services",
    "tasks",
]
