"""A parameter sweep built on ``train``."""

from collections.abc import Callable
from typing import Annotated

from opendataframework import Config, Logger, Task

from app.training import train


@Task
class Sweep:
    """Train once per learning rate in ``[task.sweep]``, so the runs can be
    compared. ``train`` arrives with its repositories already filled in.

    A task takes no arguments when it runs, so the grid comes from config:
    a different sweep is an edit to ``config.toml``, not a different call.
    """

    def __init__(
        self,
        config: Config,
        logger: Logger,
        train_once: Annotated[Callable[..., dict], train],
    ) -> None:
        """Read the grid and store what the sweep runs with.

        Args:
            config: Project config; reads ``task.sweep.learning-rates`` and
                ``task.sweep.epochs``.
            logger: The task's logger.
            train_once: ``train``, taking only the learning rate and epochs.
        """
        cfg = config.get("task").get("sweep")
        self.learning_rates = list(cfg.get("learning-rates", [0.001, 0.01, 0.1, 1.0]))
        self.epochs = int(cfg.get("epochs", 5))
        self.logger = logger
        self.train_once = train_once

    def execute(self) -> list[dict]:
        """Train each learning rate in turn and return every run's summary."""
        summaries = [self.train_once(lr, self.epochs) for lr in self.learning_rates]
        best = min(summaries, key=lambda s: s["final"]["loss"])
        self.logger.info(f"swept {len(summaries)} runs, best: {best['run']}")
        return summaries
