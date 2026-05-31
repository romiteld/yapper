"""Tests for Phase 3 formatting settings keys in constants."""
from app.core import constants


def test_output_modes_list_present():
    assert constants.OUTPUT_MODES == ["technical", "natural", "verbatim"]


def test_default_settings_has_formatting_keys():
    d = constants.DEFAULT_SETTINGS
    assert d["output_mode"] == "technical"
    assert d["expand_spoken_symbols"] is True
    assert d["vocabulary"] == []


def test_schema_validates_output_mode():
    _type, validator, _desc = constants.SETTINGS_SCHEMA["output_mode"]
    assert _type is str
    assert validator("technical") is True
    assert validator("natural") is True
    assert validator("verbatim") is True
    assert validator("slop") is False


def test_schema_validates_expand_spoken_symbols_and_vocabulary():
    assert constants.SETTINGS_SCHEMA["expand_spoken_symbols"][0] is bool
    vtype, vvalidator, _ = constants.SETTINGS_SCHEMA["vocabulary"]
    assert vtype is list
    assert vvalidator([]) is True
    assert vvalidator([{"said": None, "typed": "kubectl"}]) is True
    assert vvalidator("not-a-list") is False
