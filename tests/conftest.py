"""
tests/conftest.py — Pytest configuration and fixtures
"""

import pytest
from env.env import CodeReviewEnv
from tasks.easy import EASY_SCENARIO
from tasks.medium import MEDIUM_SCENARIO
from tasks.hard import HARD_SCENARIO


@pytest.fixture
def env():
    """Create a fresh environment instance."""
    return CodeReviewEnv()


@pytest.fixture
def easy_scenario():
    """Return easy task scenario."""
    return EASY_SCENARIO


@pytest.fixture
def medium_scenario():
    """Return medium task scenario."""
    return MEDIUM_SCENARIO


@pytest.fixture
def hard_scenario():
    """Return hard task scenario."""
    return HARD_SCENARIO
