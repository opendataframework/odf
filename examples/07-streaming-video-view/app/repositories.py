"""Live webcam repository backing the streaming-video-view example."""

import time
from collections.abc import Iterator

import cv2
from opendataframework import Config, Repository, Storage, StreamingVideoView

from app.entities import Frame


@Storage
@Repository(Frame)
class Webcam:
    """Live local webcam feed — read-only and stream-only, no get/all/save.

    The device is opened in ``open_stream()`` and released in
    ``close_stream()`` — ``Context.start_stream()``/``stop_stream()`` call
    these around the background stream thread's lifetime, so the camera is
    only actually reserved while a stream is running, not for the whole
    ``Project`` lifetime.
    """

    def __init__(self, config: Config) -> None:
        """Read the configured device index; leave the camera unopened.

        Args:
            config: Project config; reads ``webcam.device`` (default ``0``).
        """
        cfg = config.get("webcam")
        self.device = cfg.get("device", 0)
        self.capture = None

    def open_stream(self) -> None:
        """Open the configured camera device, ready to be read from."""
        self.capture = cv2.VideoCapture(self.device)

    def close_stream(self) -> None:
        """Release the camera device."""
        self.capture.release()
        self.capture = None

    def stream(self) -> Iterator[Frame]:
        """Yield JPEG-encoded frames read from the open camera device.

        Yields:
            Each captured ``Frame``, until the device stops producing frames.
        """
        frame_id = 0
        while True:
            ok, image = self.capture.read()
            if not ok:
                break
            ok, buf = cv2.imencode(".jpg", image)
            if not ok:
                continue
            frame_id += 1
            yield Frame(id=frame_id, data=buf.tobytes(), timestamp=time.time())

    def data_view(self) -> StreamingVideoView:
        """Tell the UI to render this feed as a streamed video, not a table.

        Returns:
            A ``StreamingVideoView`` keyed on the ``data`` field.
        """
        return StreamingVideoView(field="data")
