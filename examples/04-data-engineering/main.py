"""The `--template data-engineering` project layout: `SeedReadings` and
`ExportReadingsSummary` are independent @Task steps, composed by
`SetupPipeline` into a raw-to-processed ETL flow — `data/raw/` in,
`data/processed/` out, coordinated (not performed) by the Pipeline.
Run from this directory: `python main.py`.
"""

from app.pipelines import SetupPipeline

from odf.server import Server

server = Server.from_config("config.toml")  # wires the pipeline's tasks via DI
server.start()

# runs SeedReadings then ExportReadingsSummary — see pipelines.py
server.context.get(SetupPipeline).execute()

server.stop()
