"""View: AudioView, a bounded, seekable clip per record — not a live feed.

VoiceMemos implements data_view() -> AudioView instead of the default table.
The topology UI renders a list of seekable audio clips, one per record,
instead of a grid of columns. Unlike 09-streaming-audio-view's
StreamingAudioView, this repository is ReadableProtocol (all()/save()), not
StreamableProtocol — there is a genuine "every record" here.

VoiceMemos comes pre-seeded in-memory (see app/repositories.py's
_SEED_MEMOS) rather than seeded here, so there's already something to
listen to — main.py only reads the memos back. Run from this directory:
`python main.py`, or `odf run` and click "View Clips" on VoiceMemos in
the UI to play them.
"""

from app.repositories import VoiceMemos

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

memos = server.context.get(VoiceMemos)

print("All memos:")
for memo in memos.all():
    print(f"  VoiceMemo(id={memo.id}, bytes={len(memo.clip)}, recorded_at={memo.recorded_at})")

print(f"\ndata_view() -> {memos.data_view()}")

server.stop()
