"""Visual region editor server validation (synthetic documents only)."""
import hashlib
import io
import json
import pytest
from PIL import Image
from inbody_mvp.visual_editor import editor_rows
from inbody_mvp.extractor import DocumentError


def fixture():
    img = Image.new("RGB", (500, 400), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    meta = {"hash": hashlib.sha256(data).hexdigest(), "sizes": {"1": [500, 400]}}
    return data, meta


def test_manual_header_is_approved():
    data, meta = fixture()
    payload = json.dumps({"rows": [[1, "header", 0, 0, 500, 90, True, None]]})
    rows, approved = editor_rows(payload, meta, data)
    assert rows[0][1] == "header"
    assert approved[1][0]["box"] == [0, 0, 1, .225]


def test_visual_editor_rejects_out_of_bounds():
    data, meta = fixture()
    payload = json.dumps({"rows": [[1, "header", 0, 0, 900, 90, True, None]]})
    with pytest.raises(DocumentError):
        editor_rows(payload, meta, data)


def test_visual_editor_rejects_history_only():
    data, meta = fixture()
    payload = json.dumps({"rows": [[1, "history", 0, 0, 500, 90, True, None]]})
    with pytest.raises(DocumentError):
        editor_rows(payload, meta, data)
