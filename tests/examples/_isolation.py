"""Lets each examples/<n>-<name>/ test package `import app` safely.

Every example's package is conventionally named `app` (matching `odf run`'s
`--app app` default), and so is demo/'s. In one pytest process, whichever
`app` package a test file imports last "wins" in `sys.modules` for anyone
importing it later — including at *execution* time (after collection has
finished for the whole session), e.g. via `mocker.patch("app.some.module")`
in a `tests/demo/` test. A naive purge-and-never-restore approach fixes
collection-time correctness but forces a fresh, side-effecting re-import of
whichever `app` package a later test needs (observed: it made `tests/demo/`'s
Prefect-backed tests flaky, since re-importing `app.tasks` re-registers
Prefect flows and spins up a second ephemeral server).

`use_app_from` remembers whatever was cached before the *first* example
touched `sys.modules`, and `restore` (called once collection finishes,
before any test runs) puts it back exactly — so execution starts from the
same state it would have without examples/ tests in the run at all.

Re-importing `app` isn't the only side effect: `opendataframework`'s
`Namespace` subclasses (`Entity`, `Component`, `Repository`, `Service`,
`Task`, `Pipeline`, `Layer`, and `Layer`'s own built-in subclasses) each
keep a process-global name -> class registry, and registering two classes
under the same kebab-name now raises (0.2.0) instead of silently
overwriting. Several examples reuse the same entity/component names (e.g.
`Reading`), so importing example N+1's `app` while example N's
registrations are still sitting in those registries collides at import
time. `use_app_from` clears every such registry before each example's
`app` import — same "start clean" treatment as `sys.modules` — and
`restore` puts the pre-examples baseline back at the very end, mirroring
`_original_app_modules` below.
"""

import sys
from pathlib import Path

from opendataframework.namespace import Namespace

_original_app_modules: dict[str, object] | None = None
_original_namespaces: dict[type, dict[str, type]] | None = None


def _app_modules() -> dict[str, object]:
    return {
        name: mod for name, mod in sys.modules.items() if name == "app" or name.startswith("app.")
    }


def _namespace_classes() -> list[type]:
    seen: list[type] = []
    stack = list(Namespace.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls not in seen:
            seen.append(cls)
            stack.extend(cls.__subclasses__())
    return seen


def use_app_from(example_dir: Path) -> None:
    global _original_app_modules, _original_namespaces
    if _original_app_modules is None:
        _original_app_modules = _app_modules()
    if _original_namespaces is None:
        _original_namespaces = {cls: dict(cls._namespace) for cls in _namespace_classes()}

    for name in _app_modules():
        del sys.modules[name]
    for cls in _namespace_classes():
        cls._namespace.clear()

    path = str(example_dir)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)


def restore() -> None:
    global _original_app_modules, _original_namespaces

    for name in _app_modules():
        del sys.modules[name]
    if _original_app_modules:
        sys.modules.update(_original_app_modules)
    _original_app_modules = None

    for cls in _namespace_classes():
        cls._namespace.clear()
    if _original_namespaces:
        for cls, namespace in _original_namespaces.items():
            cls._namespace.update(namespace)
    _original_namespaces = None

    examples_dir = Path(__file__).resolve().parents[2] / "examples"
    prefix = str(examples_dir) + "/"
    sys.path[:] = [p for p in sys.path if not p.startswith(prefix)]
