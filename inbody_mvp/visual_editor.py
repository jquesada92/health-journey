"""Session-only visual region editor payload and server-side validation."""
import base64
import io
import json

from .section_review import COLUMNS, validate_regions
from .visual_debug import _pages
from .extractor import DocumentError

MAX_EDITOR_PAYLOAD = 12_000_000


def make_editor_payload(filename, data, rows, metadata):
    pages = []
    for number, image in _pages(filename, data):
        # Keep browser payload bounded; all coordinates retain original dimensions.
        preview = image.copy()
        preview.thumbnail((1100, 1500))
        buf = io.BytesIO()
        preview.save(buf, format="JPEG", quality=72)
        pages.append({"number": number, "width": image.width, "height": image.height,
                      "url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()})
    payload = {"pages": pages, "rows": rows, "metadata": metadata}
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded) > MAX_EDITOR_PAYLOAD:
        raise DocumentError("El documento es demasiado grande para el editor.")
    return encoded


def editor_rows(raw, metadata, data):
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
            raise ValueError()
        rows = payload["rows"]
        if not isinstance(metadata, dict):
            raise ValueError()
        if len(rows) > 50:
            raise ValueError()
        # Do not trust image, metadata, dimensions or filenames supplied by JS.
        validated = validate_regions(rows, metadata, data)
        return rows, validated
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise DocumentError("Edición visual inválida. Redetecta y revisa las secciones.") from exc
