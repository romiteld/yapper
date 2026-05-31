"""Tests for Phase 3 formatting settings keys in constants."""
from app.core import constants


def test_output_modes_list_present():
    assert constants.OUTPUT_MODES == ["clean", "polished", "verbatim"]


def test_default_settings_has_formatting_keys():
    d = constants.DEFAULT_SETTINGS
    assert d["output_mode"] == "clean"
    assert d["expand_spoken_symbols"] is True
    assert d["vocabulary"] == []


def test_schema_validates_output_mode():
    _type, validator, _desc = constants.SETTINGS_SCHEMA["output_mode"]
    assert _type is str
    assert validator("clean") is True
    assert validator("polished") is True
    assert validator("verbatim") is True
    assert validator("technical") is False  # legacy name no longer valid
    assert validator("bogus") is False


def test_schema_validates_expand_spoken_symbols_and_vocabulary():
    assert constants.SETTINGS_SCHEMA["expand_spoken_symbols"][0] is bool
    vtype, vvalidator, _ = constants.SETTINGS_SCHEMA["vocabulary"]
    assert vtype is list
    assert vvalidator([]) is True
    assert vvalidator(["kubectl", {"said": None, "typed": "nginx"}]) is True
    assert vvalidator([{"said": None, "typed": "kubectl"}]) is True
    assert vvalidator([{"said": None}]) is False
    assert vvalidator("not-a-list") is False
