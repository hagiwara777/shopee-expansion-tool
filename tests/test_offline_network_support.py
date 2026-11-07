"""Offline network guard used by shared tests."""
import socket
from threading import local

import pytest

def _deny_network_except_socketpair(monkeypatch):
    """Windows asyncio uses a loopback socketpair for its internal wakeup pipe.

    Permit only the stdlib pair constructor on this thread, not arbitrary
    loopback connections or external application/API traffic.
    """
    state = local()
    connect, socketpair = socket.socket.connect, socket.socketpair

    def no_network(sock, address):
        if (getattr(state, "creating_pair", False) and isinstance(address, tuple)
                and address[0] in {"127.0.0.1", "::1"}):
            return connect(sock, address)
        raise AssertionError("Unexpected network")

    def wakeup_pair(*args, **kwargs):
        state.creating_pair = True
        try:
            return socketpair(*args, **kwargs)
        finally:
            state.creating_pair = False

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "socketpair", wakeup_pair)


def test_network_guard_permits_windows_wakeup_pair_but_rejects_other_connections(monkeypatch):
    # Force the exact stdlib fallback used by the Windows Python 3.12 CI runner.
    monkeypatch.setattr(socket, "socketpair", socket._fallback_socketpair)
    _deny_network_except_socketpair(monkeypatch)
    first, second = socket.socketpair()
    with first, second:
        first.sendall(b"wakeup")
        assert second.recv(6) == b"wakeup"
    for address in (("127.0.0.1", 9), ("203.0.113.1", 443)):
        with socket.socket() as sock, pytest.raises(AssertionError, match="Unexpected network"):
            sock.connect(address)
