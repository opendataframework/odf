"""The `--template data-science` project layout: `data/raw/` holds source
data exactly as it arrived, `data/processed/` holds anything derived from
it, and `notebooks/` is where that derivation happens interactively.

This script does the one thing the rest of the app needs a running Server
for: loading `data/raw/readings.csv` into the `Readings` repository (backed
by `app.db`). Everything after that — the actual exploration — happens in
`notebooks/explore.ipynb`, which reads `app.db` directly, outside the
Context (see that notebook for why `@Repository` allows this).
Run from this directory: `python main.py`.
"""

import csv

from app.entities import Reading
from app.repositories import Readings

from odf.server import Server

server = Server.from_config("config.toml")  # wires Readings/SQLite via DI
server.start()

readings = server.context.get(Readings)

if readings.all():
    print("readings already loaded, skipping data/raw/readings.csv")
else:
    with open("data/raw/readings.csv", newline="") as f:
        for row in csv.DictReader(f):
            readings.save(Reading(id=None, sensor=row["sensor"], celsius=float(row["celsius"])))
    print(f"loaded {len(readings.all())} reading(s) from data/raw/readings.csv into app.db")

print("Now open notebooks/explore.ipynb to explore app.db standalone.")

server.stop()
