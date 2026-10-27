from collections.abc import Callable
from typing import Annotated

from opendataframework import Config, Logger, Task

from app.training import train


@Task
class Sweep:
    """Train once per learning rate in ``[task.sweep]``, so the runs can be
    compared. ``train`` arrives with its repositories already filled in."""

    def __init__(
        self,
        config: Config,
        logger: Logger,
        train_once: Annotated[Callable[..., dict], train],
    ) -> None:
        cfg = config.get("task").get("sweep")
        self.learning_rates = list(cfg.get("learning-rates", [0.01, 0.1, 0.5]))
        self.epochs = int(cfg.get("epochs", 6))
        self.logger = logger
        self.train_once = train_once

    def execute(self) -> list[dict]:
        summaries = [self.train_once(lr, self.epochs) for lr in self.learning_rates]
        best = min(summaries, key=lambda s: s["final"]["loss"])
        self.logger.info(f"swept {len(summaries)} runs, best: {best['run']}")
        return summaries
