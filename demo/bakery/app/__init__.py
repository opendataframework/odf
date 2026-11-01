"""The bakery's ``odf`` project: registers every class and function for ``odf run`` to discover."""

from app import clients, entities, ingest, pipelines, repositories, services, storages, tasks

__all__ = [
    "clients",
    "entities",
    "ingest",
    "pipelines",
    "repositories",
    "services",
    "storages",
    "tasks",
]
