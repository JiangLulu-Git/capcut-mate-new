"""get_transitions：转场列表与 mode 筛选。"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("ENABLE_APIKEY", "false")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from exceptions import CustomException
from src.service.get_transitions import get_transitions


def test_get_transitions_includes_dissolve() -> None:
    transitions = get_transitions(mode=0)
    names = {t["name"] for t in transitions}
    assert "叠化" in names
    dissolve = next(t for t in transitions if t["name"] == "叠化")
    assert dissolve["is_overlap"] is True
    assert dissolve["default_duration"] == 500_000


def test_get_transitions_mode_free() -> None:
    all_items = get_transitions(mode=0)
    free_items = get_transitions(mode=2)
    assert len(free_items) <= len(all_items)
    assert all(not t["is_vip"] for t in free_items)


def test_get_transitions_invalid_mode() -> None:
    with pytest.raises(CustomException):
        get_transitions(mode=3)
