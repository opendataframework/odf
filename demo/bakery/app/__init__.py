"""The bakery's ``odf`` project: registers every class and function for ``odf run`` to discover."""

from app import (
    agents,
    allergens,
    clients,
    drafts,
    entities,
    ingest,
    margins,
    model,
    pipelines,
    planning,
    purchasing,
    reactions,
    repositories,
    services,
    storages,
    tasks,
)

__all__ = [
    "agents",
    "allergens",
    "clients",
    "drafts",
    "entities",
    "ingest",
    "margins",
    "model",
    "pipelines",
    "planning",
    "purchasing",
    "reactions",
    "repositories",
    "services",
    "storages",
    "tasks",
]
