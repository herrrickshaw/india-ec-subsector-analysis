"""Shared fixtures: repo paths + synthetic PARIVESH dumps (never the live API)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# The expected outputs were generated with the pre-refactor scripts on this date.
FIXTURE_BUILT = "2026-11-02"


@pytest.fixture
def fixture_input() -> Path:
    return FIXTURES / "input"


@pytest.fixture
def fixture_expected() -> Path:
    return FIXTURES / "expected"
