"""The language model the agents can ask: a local Ollama, when there is one.

Every agent reads what it can with plain rules first, which is cheap,
deterministic and enough for the templated messages most restaurants send.
It asks the model only for what the rules can't read, and when there's no
model, it marks the draft for a person to review rather than guessing.
"""

import json
import time
import urllib.request

from opendataframework import Api, Component, Config, Logger

from app.settings import setting


@Api
@Component
class Model:
    """A local model behind Ollama's HTTP API, or nothing: ``[component.model] url`` unset.

    Answers are asked for as JSON matching a schema, at temperature 0, so an
    agent gets something it can check, not prose to parse.
    """

    # Seconds a reachability check holds for, so a missing model isn't asked every time.
    CHECK_EVERY = 30

    def __init__(self, config: Config, logger: Logger) -> None:
        """Read ``[component.model]``: ``url`` (``OLLAMA_URL``), ``name`` (``OLLAMA_MODEL``).

        Args:
            config: Project config.
            logger: The component's logger.
        """
        self.url = setting(config, "component.model", "url", "OLLAMA_URL", "").rstrip("/")
        self.name = setting(config, "component.model", "name", "OLLAMA_MODEL", "gpt-oss:20b")
        self.timeout = float(setting(config, "component.model", "timeout", "OLLAMA_TIMEOUT", 120))
        self.logger = logger
        self._checked: tuple[float, bool] = (0.0, False)

    @property
    def author(self) -> str:
        """How a draft names this model as its author: ``"model:<name>"``."""
        return f"model:{self.name}"

    def available(self) -> bool:
        """Return whether a model is configured and Ollama answers, checked at most every 30 s."""
        if not self.url:
            return False
        at, ok = self._checked
        if time.monotonic() - at < self.CHECK_EVERY:
            return ok
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=2):  # nosec B310
                ok = True
        except OSError:
            ok = False
        self._checked = (time.monotonic(), ok)
        return ok

    def ask(self, system: str, prompt: str, schema: dict) -> dict | None:
        """Ask the model, and return its answer as the JSON ``schema`` describes.

        Args:
            system: What the model is and what it must do.
            prompt: The input to work on.
            schema: The JSON schema the answer must match.

        Returns:
            The answer, or ``None`` if there's no model, it failed, or what it
            said isn't JSON. The caller still checks the answer's content.
        """
        if not self.available():
            return None
        body = json.dumps(
            {
                "model": self.name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "format": schema,
                "stream": False,
                "options": {"temperature": 0},
            }
        ).encode()
        request = urllib.request.Request(f"{self.url}/api/chat", data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
                answer = json.loads(response.read())
            return json.loads(answer["message"]["content"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.logger.warning(f"the model couldn't answer: {exc!r}")
            return None

    def details(self) -> dict[str, str]:
        """Show which model the agents ask, if any."""
        if not self.url:
            return {"model": "none", "agents": "rules only, the rest marked for review"}
        state = "reachable" if self.available() else "unreachable: rules only for now"
        return {"model": self.name, "ollama": self.url, "state": state}
