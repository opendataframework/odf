"""View: VideoView, a bounded, seekable clip per record — not a live feed.

SecurityClips implements data_view() -> VideoView instead of the default
table. The topology UI renders a list of seekable video clips, one per
record, instead of a grid of columns. Unlike 07-streaming-video-view's
StreamingVideoView, this repository is ReadableProtocol (all()/save()), not
StreamableProtocol — there is a genuine "every record" here.

SecurityClips comes pre-seeded in-memory (see app/repositories.py's
_SEED_CLIPS) rather than seeded here, so there's already something to
watch — main.py only reads the clips back. Run from this directory:
`python main.py`, or `odf run` and click "View Clips" on SecurityClips in
the UI to watch them.
"""

from app.repositories import SecurityClips

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

clips = server.context.get(SecurityClips)

print("All clips:")
for clip in clips.all():
    print(
        f"  SecurityClip(id={clip.id}, label={clip.label!r}, bytes={len(clip.clip)}, "
        f"recorded_at={clip.recorded_at})"
    )

print(f"\ndata_view() -> {clips.data_view()}")

server.stop()
