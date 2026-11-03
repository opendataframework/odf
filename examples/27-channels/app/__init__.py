"""Registers this example's ``@Entity``/``@Repository``/``@Function`` objects
for ``Server.from_config()`` to discover."""

from app import entities, functions, repositories

__all__ = ["entities", "functions", "repositories"]
