"""Offline tests may use loopback sockets, but never real camera/cloud I/O."""

import ipaddress
import socket

import pytest


@pytest.fixture(autouse=True)
def loopback_only_network(monkeypatch):
    def guard(original):
        def checked(sock, *arguments):
            address = arguments[-1]
            host = address[0]
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = host == "localhost"
            if not allowed:
                raise AssertionError("tests cannot contact camera/cloud hosts")
            return original(sock, *arguments)

        return checked

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(
            socket.socket, name, guard(getattr(socket.socket, name))
        )
