"""Pytest configuration."""
import os
import pytest

# Use in-memory SQLite for tests so runs are isolated and leave no artifacts.
os.environ["BLACKROAD_DB"] = ":memory:"


@pytest.fixture
def gateway_url():
    return "http://127.0.0.1:8787"
