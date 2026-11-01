"""Configurable, conservative OCR label/value association within approved regions.

Coordinates are normalized page fractions. Never infer numeric digits or units.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .layouts import Token, normalize_detections

Direction = Literal["top_to_bottom", "left_to_right"]
SECTION_DIRECTIONS: dict[str, Direction] = {
    "header": "top_to_bottom",
    "muscle_fat": "left_to_right",
    "body_composition": "left_to_right",
    "obesity": "left_to_right",
}

@dataclass(frozen=True)
class Association:
    label: Token
    value: Token
    direction: Direction
    score: float


def match_spatial_pairs(
    detections: list,
    width: int,
    height: int,
    *,
    direction: Direction,
    region: tuple[float, float, float, float],
    max_gap: float = .18,
    tolerance: float = .012,
    labels: tuple[str, ...] = (),
) -> list[Association]:
    """Match a known label with a number strictly inside a reviewed region.

    The numeric candidate is not parsed/rounded here: source text is preserved.
    A value is used at most once. Ties are left unresolved for human review.
    """
    import re
    if direction not in ("top_to_bottom", "left_to_right"):
        raise ValueError("Unsupported spatial direction")
    x0,y0,x1,y1 = region
    tokens = [t for t in normalize_detections(detections,width,height)
              if x0 <= t.cx <= x1 and y0 <= t.cy <= y1]
    number = re.compile(r"^[+−-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)\s*(?:kg|%|°|Ω|ohm|L|cm)?$",re.I)
    identifier = re.compile(r"^[A-Za-z0-9_-]{6,24}$")
    candidates = [t for t in tokens if number.fullmatch(t.text.strip()) or
                  (direction == "top_to_bottom" and identifier.fullmatch(t.text.strip())
                   and any(key.casefold() == "id" for key in labels))]
    key_tokens = [t for t in tokens if t not in candidates and
                  (not labels or any(label.casefold() in t.text.casefold() for label in labels))]
    matches = []
    used = set()
    for label in sorted(key_tokens,key=lambda t:(t.cy,t.cx)):
        ranked = []
        for value in candidates:
            if id(value) in used:
                continue
            if direction == "left_to_right":
                gap=value.x-(label.x+label.w)
                offset=abs(value.cy-label.cy)
            else:
                gap=value.y-(label.y+label.h)
                offset=abs(value.cx-label.cx)
            if -tolerance <= gap <= max_gap and offset <= tolerance:
                ranked.append((max(gap,0)+offset*2,value))
        ranked.sort(key=lambda item:item[0])
        if not ranked or (len(ranked)>1 and abs(ranked[0][0]-ranked[1][0])<.002):
            continue
        score,value=ranked[0]
        used.add(id(value))
        matches.append(Association(label,value,direction,score))
    return matches
