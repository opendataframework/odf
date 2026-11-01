"""Reading a setting from the environment first, then ``config.toml``.

Secrets (API tokens, webhook secrets, the mailbox password) come from the
environment, set by ``compose.yaml`` from ``.env``. Everything else has a
sensible value in ``config.toml``, which the environment can still override.
"""

import os

from opendataframework import Config


def setting(config: Config, section: str, key: str, env: str, default: object = "") -> str:
    """Return ``$env`` if set, else ``key`` in ``[section]``, else ``default``, as a string.

    Args:
        config: The project's config.
        section: A dotted table, such as ``"component.pos"``.
        key: The key in that table.
        env: The environment variable that overrides it.
        default: Used when neither has it.
    """
    value = os.environ.get(env)
    if value:
        return value
    table = config
    for part in section.split("."):
        table = table.get(part)
    return str(table.get(key, default))
