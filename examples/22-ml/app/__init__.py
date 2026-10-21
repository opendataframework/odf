"""Registers this example's ``@Entity``/``@Repository``/``@Component``/
``@Function``/``@Task`` objects for ``Server.from_config()`` to discover."""

from app import charts, entities, exports, repositories, storages, tasks, training

__all__ = [
    "charts",
    "entities",
    "exports",
    "repositories",
    "storages",
    "tasks",
    "training",
]
