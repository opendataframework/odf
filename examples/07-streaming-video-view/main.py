"""View: StreamingVideoView, a live feed instead of a bounded record list.

Webcam is stream-only (StreamableProtocol) — no all()/save() — and its
data_view() -> StreamingVideoView tells the dev UI to render a live player
with a Start/Stop toggle instead of a table. Needs a physical webcam at the
configured device index. Run from this directory: `python main.py` to pull a
few frames directly, or `odf run` and click "Start Streaming" then
"View Stream" on Webcam in the UI to watch the live feed.
"""

import itertools

from app.repositories import Webcam

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

webcam = server.context.get(Webcam)

print(f"data_view() -> {webcam.data_view()}")

webcam.open_stream()
try:
    print("First 3 frames:")
    for frame in itertools.islice(webcam.stream(), 3):
        print(f"  Frame(id={frame.id}, bytes={len(frame.data)}, timestamp={frame.timestamp})")
finally:
    webcam.close_stream()

server.stop()
