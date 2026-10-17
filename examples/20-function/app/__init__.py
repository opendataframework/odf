"""Registers this example's ``@Entity``/``@Repository``/``@Component``/
``@Function``/``@Task`` objects for ``Server.from_config()`` to discover."""

from app import components, entities, reports, repositories, tasks

__all__ = [
    "components",
    "entities",
    "repositories",
    "reports",
    "tasks",
]
