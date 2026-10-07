"""Persists image annotations drawn in the UI to a JSON sidecar file.

Backs the labelled boxes drawn over an open image in the image view (see
``app.js``'s "Image annotations" section), so a project can label images in
the dev UI and read the result from a later pipeline with nothing more than
``json.load``. Scoped to whatever ``Path`` a ``UiServer`` is constructed with,
like ``odf.ui.layout`` (see ``Server.start``'s ``annotations-file`` config
key).

The file holds one block per repository id::

    {
      "version": 1,
      "repositories": {
        "delivery-photos": {
          "labels": ["parcel", "door"],
          "records": {
            "1": {
              "width": 1280,
              "height": 960,
              "annotations": [
                {"type": "box", "label": "parcel",
                 "x": 412, "y": 230, "width": 310, "height": 188}
              ]
            }
          }
        }
      }
    }

``labels`` holds the labels the repository's boxes use, in the order each was
first used. A label no box uses any more is dropped, so a label's index is a
stable class id only while every label before it stays in use. Coordinates
are pixels in the image as displayed (``x``/``y`` the box's top-left corner),
and each record carries the image's own ``width`` and ``height`` so they can
be normalised without decoding the image.
"""

import json
import os
from pathlib import Path

VERSION = 1


def load(path: Path) -> dict:
    """Return the saved annotations, or an empty document if the file is absent.

    Unlike ``odf.ui.layout.load``, a file that exists but can't be parsed
    raises rather than reading as empty: the next save would otherwise replace
    someone's labelling work with a blank document.

    Args:
        path: Location of the annotations JSON file.

    Returns:
        The document described in the module docstring.

    Raises:
        ValueError: If the file exists but isn't a JSON object.
    """
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {"version": VERSION, "repositories": {}}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    data.setdefault("version", VERSION)
    data.setdefault("repositories", {})
    return data


def save(path: Path, data: dict) -> None:
    """Write the annotations document, replacing any existing file atomically.

    Args:
        path: Location of the annotations JSON file. Parent directories are
            created as needed.
        data: The document described in the module docstring.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(tmp, path)


def repository(data: dict, repo_id: str) -> dict:
    """Return one repository's block, or an empty one if it has no annotations.

    Args:
        data: The document described in the module docstring.
        repo_id: The repository's kebab-case id.

    Returns:
        ``{"labels": [...], "records": {...}}``.
    """
    block = data.get("repositories", {}).get(repo_id, {})
    return {"labels": list(block.get("labels", [])), "records": dict(block.get("records", {}))}


def set_record(
    data: dict, repo_id: str, key: str, width: object, height: object, annotations: object
) -> dict:
    """Replace one record's annotations in ``data``, in place.

    Labels not seen before in this repository are appended to its ``labels``,
    and labels none of its boxes use any more are dropped from it. An empty
    ``annotations`` removes the record's entry.

    Args:
        data: The document described in the module docstring.
        repo_id: The repository's kebab-case id.
        key: The record's key, as it appears in the URL.
        width: The image's width in pixels.
        height: The image's height in pixels.
        annotations: The record's full list of annotations.

    Returns:
        The repository's updated block, as ``repository()`` returns it.

    Raises:
        ValueError: If the image size or any annotation is malformed.
    """
    image_width = _positive_int(width, "width")
    image_height = _positive_int(height, "height")
    if not isinstance(annotations, list):
        raise ValueError("annotations must be a list")
    boxes = [_box(item, image_width, image_height) for item in annotations]

    block = data.setdefault("repositories", {}).setdefault(repo_id, {})
    records = block.setdefault("records", {})
    if boxes:
        records[key] = {"width": image_width, "height": image_height, "annotations": boxes}
    else:
        records.pop(key, None)
    used = {box["label"] for record in records.values() for box in record["annotations"]}
    labels = [label for label in block.get("labels", []) if label in used]
    for box in boxes:
        if box["label"] not in labels:
            labels.append(box["label"])
    block["labels"] = labels
    return repository(data, repo_id)


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return value


def _positive_int(value: object, name: str) -> int:
    result = round(_number(value, name))
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _box(item: object, image_width: int, image_height: int) -> dict:
    """Validate one annotation and clamp it to the image."""
    if not isinstance(item, dict) or item.get("type") != "box":
        raise ValueError('each annotation must be an object with "type": "box"')
    label = item.get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("each annotation needs a non-empty label")
    left = round(_number(item.get("x"), "x"))
    top = round(_number(item.get("y"), "y"))
    right = left + _positive_int(item.get("width"), "width")
    bottom = top + _positive_int(item.get("height"), "height")
    left, right = max(left, 0), min(right, image_width)
    top, bottom = max(top, 0), min(bottom, image_height)
    if right <= left or bottom <= top:
        raise ValueError("annotation lies outside the image")
    return {
        "type": "box",
        "label": label.strip(),
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }
