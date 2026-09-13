"""Offline-only tests: isolate HOME before importing application modules."""
import os
import socket
import tempfile

import pytest

_HOME = tempfile.TemporaryDirectory(prefix="wraith-test-home-")
os.environ["HOME"] = _HOME.name


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Live network access is forbidden in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
