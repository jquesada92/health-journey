"""Synthetic OCR decimal safety checks for segmental body composition."""
from inbody_mvp.layouts_es import _choose, cell
from inbody_mvp.layouts import Token


def sample(metric, unit, raw):
    spec = cell(metric, "segmental", unit, "segmental", "mass",
                .5, .65, dx=.04, dy=.01, bounds=(0, 400))
    token = Token(raw, .49, .645, .02, .01, .99)
    return _choose([token], spec)


def test_preserves_valid_decimal_mass_and_percent():
    assert sample("segmental_lean_mass", "kg", "4.07kg")[0] == 4.07
    assert sample("segmental_fat_mass", "kg", "0.5kg")[0] == .5
    assert sample("segmental_lean_reference_percentage", "%", "133.8%")[0] == 133.8
    assert sample("segmental_fat_reference_percentage", "%", "210.7%")[0] == 210.7


def test_does_not_invent_missing_decimal_point():
    assert sample("segmental_lean_mass", "kg", "407kg") is None
    assert sample("segmental_fat_mass", "kg", "500kg") is None
    assert sample("segmental_lean_reference_percentage", "%", "1338%") is None
    assert sample("segmental_fat_reference_percentage", "%", "2107%") is None
