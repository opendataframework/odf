"""The `--template research` project layout: `data/` holds raw, read-only
source data, `results/` holds everything an experiment generates, and
`doc/notes.md` is a lab-notebook stub — hypothesis, method, results, notes.

`RunExperiment` (unlike 04-data-engineering's SeedItems/ExportItemsSummary
split) both loads and computes in one Task: closer to how an experiment
script actually gets rerun by hand while iterating.
Run from this directory: `python main.py`.
"""

from app.experiments import RunExperiment

from odf.server import Server

server = Server.from_config("config.toml")  # wires RunExperiment/Readings via DI
server.start()

# loads data/readings.csv (if not already loaded), then computes and persists
result = server.context.get(RunExperiment).execute()
print(f"Experiment result: {result}")

server.stop()
