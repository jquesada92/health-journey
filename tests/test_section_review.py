"""Synthetic tests: user-reviewed regions and upload identity."""
import hashlib
import io

import pytest
from PIL import Image

from inbody_mvp.extractor import DocumentError
from inbody_mvp.section_review import COLUMNS, validate_regions, propose_regions


def sample():
    buffer = io.BytesIO()
    Image.new("RGB", (240, 300), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_reviewed_region_is_normalized():
    data = sample()
    meta = {"hash": hashlib.sha256(data).hexdigest(), "sizes": {"1": [240, 300]}}
    rows = [[1, "impedance", 24, 60, 144, 180, True, 0.9]]
    chosen = validate_regions(rows, meta, data)
    assert chosen[1][0]["section"] == "impedance"
    assert chosen[1][0]["box"] == [0.1, 0.2, 0.6, 0.6]


def test_unknown_and_history_never_extracted():
    data = sample()
    meta = {"hash": hashlib.sha256(data).hexdigest(), "sizes": {"1": [240, 300]}}
    with pytest.raises(DocumentError):
        validate_regions([[1, "history", 0, 0, 50, 60, True, .9]], meta, data)


def test_rejects_edited_file_and_out_of_bounds():
    data = sample()
    meta = {"hash": "bad", "sizes": {"1": [240, 300]}}
    row = [[1, "impedance", 0, 0, 500, 60, True, .9]]
    with pytest.raises(DocumentError):
        validate_regions(row, meta, data)
    meta["hash"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(DocumentError):
        validate_regions(row, meta, data)


def test_detector_results_are_pending_classification(monkeypatch):
    from inbody_mvp import section_review
    from inbody_mvp.section_ai import LayoutRegion
    monkeypatch.setattr(section_review, "ai_detect_layout",
                        lambda image: [LayoutRegion("table", .93, (10, 20, 100, 200))])
    rows, meta = propose_regions("sample.png", sample())
    assert rows[0][1] == "other"
    assert rows[0][2:6] == [10, 20, 100, 200]
    assert meta["sizes"]["1"] == [240, 300]
