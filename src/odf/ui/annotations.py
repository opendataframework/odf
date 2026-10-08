"""Persists annotations drawn in the UI to a JSON sidecar file.

Backs the labelled boxes drawn over an open image in the image view, the
labelled text spans and page boxes drawn on an open document in the document
view, and the labelled time ranges and points marked on the chart of the
timeseries view (see ``app.js``'s "Image annotations", "Document annotations"
and "Timeseries annotations" sections), so a project can label its data in
the dev UI and read the result
from a later pipeline with nothing more than ``json.load``. Scoped to whatever
``Path`` a ``UiServer`` is constructed with, like ``odf.ui.layout`` (see
``Server.start``'s ``annotations-file`` config key).

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
        },
        "order-receipts": {
          "labels": ["total", "logo"],
          "records": {
            "3": {
              "annotations": [
                {"type": "span", "label": "total",
                 "start": 120, "end": 127, "text": "$100.00"}
              ]
            },
            "4": {
              "annotations": [
                {"type": "box", "label": "logo", "page": 1,
                 "x": 40, "y": 32.5, "width": 120, "height": 48,
                 "page_width": 612, "page_height": 792}
              ]
            }
          }
        },
        "orders": {
          "labels": ["promo", "outlier"],
          "annotations": [
            {"type": "range", "label": "promo",
             "start": 1787782427.2, "end": 1787955227.2},
            {"type": "point", "label": "outlier",
             "at": 1787868827.2, "key": "2"}
          ]
        }
      }
    }

``labels`` holds the labels the repository's annotations use, in the order
each was first used. A label no annotation uses any more is dropped, so a
label's index is a stable class id only while every label before it stays in
use.

An image's coordinates are pixels in the image as displayed (``x``/``y`` the
box's top-left corner), and each record carries the image's own ``width`` and
``height`` so they can be normalised without decoding the image.

A document's record has no size of its own. A span's ``start`` and ``end``
(exclusive) count Unicode code points, as a Python ``str`` is indexed, into
the document's text: the field's ``str`` value, or its bytes decoded as
UTF-8. ``text`` is the text the span covered when it was drawn, so a reader
can tell a document that has changed since. Spans in one record don't overlap
and are kept in the order they appear in the text. A box on a PDF page is in
PDF points from the top-left corner of the page as displayed, with ``page``
counted from 1 and the page's own size beside it.

A timeseries repository's annotations belong to its time axis rather than to
one record, so its block holds them in one ``annotations`` list and has no
``records``. A range's ``start`` and ``end`` and a point's ``at`` are values
of the view's timestamp field, in that field's own units. A point is made on
a record: ``at`` is that record's timestamp and ``key`` its key, as a string.
The list is kept in time order, and ranges may overlap.
"""

import json
import math
import os
from itertools import pairwise
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
    record = {"width": image_width, "height": image_height, "annotations": boxes}
    return _store(data, repo_id, key, record)


def set_document_record(data: dict, repo_id: str, key: str, annotations: object) -> dict:
    """Replace one document record's annotations in ``data``, in place.

    Labels are kept as ``set_record`` keeps them, and an empty ``annotations``
    removes the record's entry.

    Args:
        data: The document described in the module docstring.
        repo_id: The repository's kebab-case id.
        key: The record's key, as it appears in the URL.
        annotations: The record's full list of annotations: text spans, boxes
            on PDF pages, or both.

    Returns:
        The repository's updated block, as ``repository()`` returns it.

    Raises:
        ValueError: If any annotation is malformed, or two spans overlap.
    """
    if not isinstance(annotations, list):
        raise ValueError("annotations must be a list")
    items = [_document_item(item) for item in annotations]
    spans = sorted(
        (item for item in items if item["type"] == "span"), key=lambda span: span["start"]
    )
    for before, after in pairwise(spans):
        if after["start"] < before["end"]:
            raise ValueError("spans must not overlap")
    boxes = [item for item in items if item["type"] == "box"]
    return _store(data, repo_id, key, {"annotations": spans + boxes})


def series(data: dict, repo_id: str) -> dict:
    """Return a timeseries repository's block, or an empty one if it has no annotations.

    Args:
        data: The document described in the module docstring.
        repo_id: The repository's kebab-case id.

    Returns:
        ``{"labels": [...], "annotations": [...]}``.
    """
    block = data.get("repositories", {}).get(repo_id, {})
    return {
        "labels": list(block.get("labels", [])),
        "annotations": list(block.get("annotations", [])),
    }


def set_series(data: dict, repo_id: str, annotations: object) -> dict:
    """Replace a timeseries repository's annotations in ``data``, in place.

    Labels are kept as ``set_record`` keeps them.

    Args:
        data: The document described in the module docstring.
        repo_id: The repository's kebab-case id.
        annotations: The repository's full list of annotations: time ranges,
            points, or both.

    Returns:
        The repository's updated block, as ``series()`` returns it.

    Raises:
        ValueError: If any annotation is malformed.
    """
    if not isinstance(annotations, list):
        raise ValueError("annotations must be a list")
    items = [_series_item(item) for item in annotations]
    block = data.setdefault("repositories", {}).setdefault(repo_id, {})
    block["annotations"] = sorted(
        items, key=lambda item: item["start"] if item["type"] == "range" else item["at"]
    )
    _keep_labels(block, items, items)
    return series(data, repo_id)


def _store(data: dict, repo_id: str, key: str, record: dict) -> dict:
    """Put ``record`` under ``key``, or drop the key if it has no annotations."""
    items = record["annotations"]
    block = data.setdefault("repositories", {}).setdefault(repo_id, {})
    records = block.setdefault("records", {})
    if items:
        records[key] = record
    else:
        records.pop(key, None)
    _keep_labels(
        block, [item for saved in records.values() for item in saved["annotations"]], items
    )
    return repository(data, repo_id)


def _keep_labels(block: dict, used: list[dict], added: list[dict]) -> None:
    """Drop the labels none of ``used`` has, then append the new ones of ``added``."""
    in_use = {item["label"] for item in used}
    labels = [label for label in block.get("labels", []) if label in in_use]
    for item in added:
        if item["label"] not in labels:
            labels.append(item["label"])
    block["labels"] = labels


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
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
    label = _label(item)
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
        "label": label,
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _label(item: dict) -> str:
    label = item.get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("each annotation needs a non-empty label")
    return label.strip()


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a whole number")
    return value


def _positive(value: object, name: str) -> float:
    result = round(_number(value, name), 2)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _document_item(item: object) -> dict:
    """Validate one annotation of a document: a text span or a box on a page."""
    kind = item.get("type") if isinstance(item, dict) else None
    if kind == "span":
        return _span(item)
    if kind == "box":
        return _page_box(item)
    raise ValueError('each annotation must be an object with "type": "span" or "box"')


def _span(item: dict) -> dict:
    label = _label(item)
    start = _whole(item.get("start"), "start")
    end = _whole(item.get("end"), "end")
    if start < 0 or end <= start:
        raise ValueError("a span needs 0 <= start < end")
    text = item.get("text")
    if not isinstance(text, str) or len(text) != end - start:
        raise ValueError("a span's text must be end - start characters long")
    return {"type": "span", "label": label, "start": start, "end": end, "text": text}


def _page_box(item: dict) -> dict:
    """Validate a box on a PDF page and clamp it to the page."""
    label = _label(item)
    page = _whole(item.get("page"), "page")
    if page < 1:
        raise ValueError("page must be 1 or more")
    page_width = _positive(item.get("page_width"), "page_width")
    page_height = _positive(item.get("page_height"), "page_height")
    left = _number(item.get("x"), "x")
    top = _number(item.get("y"), "y")
    right = left + _positive(item.get("width"), "width")
    bottom = top + _positive(item.get("height"), "height")
    left, right = max(left, 0), min(right, page_width)
    top, bottom = max(top, 0), min(bottom, page_height)
    if right <= left or bottom <= top:
        raise ValueError("annotation lies outside the page")
    return {
        "type": "box",
        "label": label,
        "page": page,
        "x": round(left, 2),
        "y": round(top, 2),
        "width": round(right - left, 2),
        "height": round(bottom - top, 2),
        "page_width": page_width,
        "page_height": page_height,
    }


def _series_item(item: object) -> dict:
    """Validate one annotation of a timeseries: a time range or a point."""
    kind = item.get("type") if isinstance(item, dict) else None
    if kind == "range":
        return _range(item)
    if kind == "point":
        return _series_point(item)
    raise ValueError('each annotation must be an object with "type": "range" or "point"')


def _range(item: dict) -> dict:
    label = _label(item)
    start = _number(item.get("start"), "start")
    end = _number(item.get("end"), "end")
    if end <= start:
        raise ValueError("a range needs start < end")
    return {"type": "range", "label": label, "start": start, "end": end}


def _series_point(item: dict) -> dict:
    label = _label(item)
    at = _number(item.get("at"), "at")
    key = item.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("a point needs the key of its record")
    return {"type": "point", "label": label, "at": at, "key": key}
