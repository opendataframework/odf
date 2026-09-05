"""View: StreamingAudioView, a live audio feed instead of a bounded list.

DispatchRadio is stream-only (StreamableProtocol) — no all()/save() — and
its data_view() -> StreamingAudioView tells the dev UI to render a live
player with a Start/Stop toggle instead of a table. Unlike
07-streaming-video-view's Webcam, there's no external device to open or
release — a pure-stdlib tone generator is the entire resource. Run from
this directory: `python main.py` to pull a few chunks directly, or
`odf run` and click "Start Streaming" then "View Stream" on DispatchRadio
in the UI.
"""

import itertools

from app.repositories import DispatchRadio

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

radio = server.context.get(DispatchRadio)

print(f"data_view() -> {radio.data_view()}")

print("First 2 chunks:")
for chunk in itertools.islice(radio.stream(), 2):
    print(f"  DispatchChunk(id={chunk.id}, bytes={len(chunk.data)}, timestamp={chunk.timestamp})")

server.stop()
