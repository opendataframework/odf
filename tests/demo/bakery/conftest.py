"""Points `import app` and `import tools` at demo/bakery for this directory's
collection. See `tests/examples/_isolation.py`.

The simulated tools open their SQLite file when imported, so `DATA_DIR`
points them at a throwaway directory first, and `WORLD_URL` at a closed port,
so they fall back to real time at once instead of looking for the world
service."""

import os
import tempfile
from pathlib import Path

from examples._isolation import use_app_from

DEMO_DIR = Path(__file__).resolve().parents[3] / "demo" / "bakery"

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="bakery-tools-"))
os.environ.setdefault("WORLD_URL", "http://127.0.0.1:9")
use_app_from(DEMO_DIR)
