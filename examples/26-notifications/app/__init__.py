"""Registers this example's ``@Entity``/``@Repository``/``@Function``/``@Service``/
``@Component``/``@Task`` objects for ``Server.from_config()`` to discover."""

from app import components, entities, functions, repositories, services, tasks

__all__ = [
    "components",
    "entities",
    "functions",
    "repositories",
    "services",
    "tasks",
]
