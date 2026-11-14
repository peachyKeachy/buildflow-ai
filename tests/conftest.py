from copy import deepcopy
from unittest.mock import Mock, patch
import socket

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
def no_external_network(monkeypatch):
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

    def guarded(method):
        def call(sock, address):
            # Windows asyncio uses a loopback TCP socketpair for its internal wakeup pipe.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return method(sock, address)
            raise AssertionError("Automated tests must not make external network calls")
        return call

    monkeypatch.setattr(socket.socket, "connect", guarded(connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(connect_ex))


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


@pytest.fixture(scope="session")
def local_models():
    from backend.retrieval_models import LocalModels

    return LocalModels()
