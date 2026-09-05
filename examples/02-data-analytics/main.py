"""The `--template data-analytics` project layout: a `Readings` repository
feeding an `@Analytics @Task` that writes a JSON report to `reports/`.

Same Task/Layer concepts as 04 and 05, applied to the shape `odf init
--template data-analytics` scaffolds: a `reports/` folder holding derived
artifacts, separate from the database itself.

`odf run` is a thin CLI wrapper around building a Server from config and
calling start(ui=True). This script does the same two steps directly in
Python, like ../01-table-view/main.py, then goes further: it seeds a few
readings, runs `SummarizeReadings` headlessly via `server.context.get(...)`,
and only then starts the UI — showing that a plain script can drive a
Server through arbitrary setup a bare `odf run` can't express.

Server wraps a plain `opendataframework.Project` rather than subclassing
it, and `.context` is delegated straight through — `server.context` here
*is* the wrapped Project's `Context`, the same one `Project.start()` would
have resolved on its own.
"""

from app.analytics import SummarizeReadings
from app.entities import Reading
from app.repositories import Readings

from odf.server import Server

server = Server.from_config("config.toml")
server.start(ui=True)

readings = server.context.get(Readings)
readings.save(Reading(id=None, sensor="kitchen", celsius=21.5))
readings.save(Reading(id=None, sensor="kitchen", celsius=22.0))
readings.save(Reading(id=None, sensor="garage", celsius=17.25))

# resolve the @Analytics @Task and run it — writes reports/summary.json
summary = server.context.get(SummarizeReadings).execute()
print(f"Report: {summary}")

print(f"UI running at {server.ui_url}")
print("Press Ctrl+C to stop")

server.wait()
