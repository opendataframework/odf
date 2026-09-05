"""Points `import app` at examples/17-custom-icon/app for this directory's
collection. See `tests/examples/_isolation.py`."""

from pathlib import Path

from examples._isolation import use_app_from

EXAMPLE_DIR = Path(__file__).resolve().parents[3] / "examples" / "17-custom-icon"

use_app_from(EXAMPLE_DIR)
