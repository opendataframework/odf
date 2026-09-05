# 09 — Streaming Audio View

A single `DispatchRadio` repository, stream-only (`StreamableProtocol`, no
`all()`/`save()`) with `data_view() -> StreamingAudioView`. The topology UI
renders it as a live audio player with a Start/Stop toggle instead of a
table or a list of clips.

This is the audio counterpart to
[`07-streaming-video-view`](../07-streaming-video-view): same live-feed
mechanism (`StreamableProtocol`, not `ReadableProtocol`), different media.
Unlike `Webcam`, there's no external device to open/release — a pure-stdlib
tone generator is the entire resource, so `DispatchRadio` implements neither
`open_stream()` nor `close_stream()` (both are optional, see
[`docs/repository.md`](../../docs/repository.md)). See
[`10-audio-view`](../10-audio-view) for the bounded, seekable counterpart.

## Structure

```
09-streaming-audio-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — opens the stream and pulls a few chunks
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── audio.py          # synth_melody_wav() — stdlib wave/struct melody synth
    ├── entities.py        # DispatchChunk(id, data, timestamp) — @Entity
    └── repositories.py    # DispatchRadio — @Storage @Repository(DispatchChunk), stream-only
```

## Dependencies

None beyond `opendataframework` itself and the Python standard library — `synth_melody_wav()`
uses only `wave`/`struct`/`math`, no ffmpeg or audio library.

## Run it

```bash
cd examples/09-streaming-audio-view
python main.py
```

Takes about 10s — `DispatchRadio` paces itself to real time (see below) so
the second chunk isn't ready until the first one's nominal 10s duration has
elapsed. Expected output (byte counts and timestamps will vary):

```
data_view() -> StreamingAudioView(field='data')
First 2 chunks:
  DispatchChunk(id=1, bytes=160044, timestamp=1788040884.201757)
  DispatchChunk(id=2, bytes=160044, timestamp=1788040894.226938)
```

Or start the dev UI and use `DispatchRadio`'s **Start Streaming** then
**View Stream** actions:

```bash
odf run
```

`GET /api/repositories` reports `DispatchRadio`'s view as
`{"kind": "streaming-audio", "field": "data"}` — that's what tells the UI to
render a live player instead of a table.

Each `/stream` request returns one complete, independently decodable WAV
clip rather than one multiplexed connection like
[`07-streaming-video-view`](../07-streaming-video-view)'s MJPEG —
`multipart/x-mixed-replace` has no browser support for `<audio>`. Every
chunk boundary forces the `<audio>` element to reload its decode pipeline
for the next clip (comparable to an HLS segment switch) — no amount of
client-side prefetching removes that reload, only how often it happens.
`_CHUNK_DURATION_SECONDS` is set to 10s (rather than something closer to
1s) specifically so that reload is rare enough to read as one continuous
station instead of a new track starting every few seconds.

`_INTERVAL_SECONDS` (the sleep between yields in `stream()`) is paced to
match `_CHUNK_DURATION_SECONDS`, not shorter — this matters more than it
looks. `Context`'s per-subscriber stream queue holds only the single
newest unconsumed item (`opendataframework.context._publish_latest`),
which is correct for a live feed like video where a slow viewer should
always see the freshest frame. But it means a producer running faster
than real time generates many chunks between two browser requests, and
the one actually delivered is whichever happened to be newest — an
effectively arbitrary jump forward in the melody, not the next
chronological chunk. That jump, not the `<audio>` reload itself, is what
made the melody sound like it broke and restarted at every chunk
boundary. Pacing production to real time means the queue's "keep only the
newest" behavior never has more than one chunk to choose between, so the
delivered chunk is always the true next one.

Chunk length and melody tempo are deliberately independent: `_PHRASE` (a
full A3-to-A4-and-back run through `_SCALE_HZ`, `_NOTE_SECONDS` each note,
plus a trailing rest) sets how fast and how far the tune moves, and
`_PHRASES_PER_CHUNK` is just how many full phrases fit in one chunk — so
the tune can move at its own tempo without forcing more frequent `<audio>`
reloads. `_CHUNK_DURATION_SECONDS` is *derived* from `_PHRASE_SECONDS *
_PHRASES_PER_CHUNK` (one full phrase, 10s total) rather than picked
independently — that's what guarantees every chunk boundary lands exactly
inside the phrase's trailing rest instead of mid-note. So whatever the
`<audio>` reload costs lands inside a beat that was already going to be
silent, rather than sounding like a cut. `synth_melody_wav()` carries its
sine phase across
notes *and* across chunk-boundary calls instead of restarting at 0 each
time (a discontinuous *phase* — not just a discontinuous frequency — is
what causes an audible click); a rest resets phase to 0 so the note after
it starts cleanly at a zero-crossing, matching the rest's own silence.
`DispatchRadio` also carries the melody's position across chunks, so the
tune keeps moving through `_PHRASE` on a loop instead of restarting every
chunk. The dev UI's player also prefetches the next chunk while the
current one is still playing (see `playAudioStream()` in
`odf/ui/static/index.html`), hiding the fetch round-trip on top of that.

The player also skips the native `<audio controls>` UI entirely — each
chunk is a complete, bounded WAV file, so a native seek bar would show
*that chunk's* duration/position, implying a scrubbable track rather than
an unbounded live feed. Instead `showStreamView()` renders a small custom
bar: a play/pause button that only pauses local listening (independent of
the Start/Stop toggle that controls the underlying stream), and a status
indicator that starts as `BUFFERING…` and switches to a pulsing `LIVE`
once the first chunk actually starts playing. That first wait is real,
not decorative — subscribing to an already-running stream attaches to a
queue that holds only the single newest not-yet-delivered chunk (see
`_INTERVAL_SECONDS` above), and a brand new subscriber starts with
nothing queued, so it can wait up to one full chunk period (~10s) for the
producer's next tick. `BUFFERING…` exists so that wait reads as expected
startup behavior instead of a broken player.
