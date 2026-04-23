"""Shared pytest fixtures.

Env vars and sys.path must be configured BEFORE `main` is imported,
because main.py instantiates the OpenAI client at import time.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("RENTCAST_API_KEY", "test-rentcast-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_pipeline(num_requests=1):
    pipe = MagicMock()
    pipe.execute.return_value = (0, 1, num_requests, True)
    return pipe


@pytest.fixture
def mock_redis(monkeypatch):
    """Replace main.redis_client with a MagicMock configured for common cases."""
    import main
    fake = MagicMock()
    fake.get.return_value = None  # default: no cached value
    fake.pipeline.return_value = _make_pipeline(num_requests=1)
    monkeypatch.setattr(main, "redis_client", fake)
    return fake


@pytest.fixture
def mock_openai(monkeypatch):
    """Replace main.client with a mock whose chat completion returns 'Mocked AI reply'."""
    import main
    fake = MagicMock()
    reply = MagicMock()
    reply.choices = [MagicMock()]
    reply.choices[0].message.content = "Mocked AI reply"
    fake.chat.completions.create = AsyncMock(return_value=reply)
    monkeypatch.setattr(main, "client", fake)
    return fake


@pytest.fixture
def test_client(mock_redis, mock_openai):
    """FastAPI TestClient with redis and openai already mocked."""
    import main
    from fastapi.testclient import TestClient
    return TestClient(main.app)
