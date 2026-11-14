from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# Never load local credentials or construct a real provider during test collection.
with patch("dotenv.load_dotenv"), patch("anthropic.Anthropic"):
    from backend import main, claude_service, project_service


@pytest.fixture(autouse=True)
def isolated_projects(monkeypatch):
    data = deepcopy(project_service.projects)
    monkeypatch.setattr(project_service, "projects", data)
    monkeypatch.setattr(main, "projects", data)


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    client = Mock()
    client.messages.create.side_effect = AssertionError("Unexpected provider call")
    monkeypatch.setattr(claude_service, "client", client)
    monkeypatch.setattr(claude_service, "load_dotenv", Mock(side_effect=AssertionError("Tests must not read .env")))
    return client


@pytest.fixture
def api():
    with TestClient(main.app) as client:
        yield client
