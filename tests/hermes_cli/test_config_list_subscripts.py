"""Bracket subscripts in ``hermes config set`` resolve to real list indices.

Regression: ``hermes config set "options[0].model" x`` wrote a literal ``"options[0]"`` key and
reported success, so the write never reached the list the runtime reads.
"""

import pytest

from hermes_cli.config import _get_nested, _set_nested, _split_key_path


def test_bracket_subscript_expands_to_numeric_segment():
    assert _split_key_path("options[0].reasoning_effort") == [
        "options", "0", "reasoning_effort"]


def test_multiple_subscripts_expand():
    assert _split_key_path("a[0][2].b") == ["a", "0", "2", "b"]


def test_plain_segments_are_untouched():
    assert _split_key_path("delegation.backends.model_map.default") == [
        "delegation", "backends", "model_map", "default"]


def test_non_numeric_subscript_stays_literal():
    """A config key may legitimately contain brackets; only all-digit subscripts are sugar."""
    assert _split_key_path("a[b].c") == ["a[b]", "c"]


def test_escaped_dot_still_works_alongside_subscripts():
    assert _split_key_path(r"options[0].grok-4\.6.context") == [
        "options", "0", "grok-4.6", "context"]


def test_set_nested_writes_list_item_not_literal_key():
    config = {"options": [{"name": "fast", "reasoning_effort": "high"}]}

    _set_nested(config, "options[0].reasoning_effort", "medium")

    assert config["options"][0]["reasoning_effort"] == "medium"
    assert "options[0]" not in config
    assert _get_nested(config, "options[0].reasoning_effort") == "medium"


def test_set_nested_out_of_range_index_fails_loudly():
    config = {"options": [{"name": "fast"}]}

    with pytest.raises(IndexError, match="out of range"):
        _set_nested(config, "options[4].name", "medium")


def test_set_nested_still_grows_dicts_on_index_free_paths():
    config = {}

    _set_nested(config, "delegation.backends.model_map.default", "deep")

    assert config == {"delegation": {"backends": {"model_map": {"default": "deep"}}}}
