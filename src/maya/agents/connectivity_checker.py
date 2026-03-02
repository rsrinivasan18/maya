"""
MAYA Connectivity Checker - Session 8
======================================
Checks whether the device has internet access.

Method: Attempt a TCP connection to a reliable host (Google DNS: 8.8.8.8:53).
- Uses only Python stdlib (socket) — zero extra dependencies
- No DNS resolution needed — direct IP:port connect
- Timeout configurable via settings (default 2 seconds)
- Any failure → returns False (offline) — MAYA always continues with Ollama

LEARNING NOTES for Srinivasan:
--------------------------------
Why 8.8.8.8:53?
  - 8.8.8.8 is Google's public DNS server — one of the most reliable IPs on the internet
  - Port 53 is the DNS port — always open on a working internet connection
  - A raw TCP connect (no HTTP) is the fastest, lightest way to check connectivity
  - If this fails, the internet is genuinely down or we're in airplane mode

Why not ping sarvam.ai?
  - Requires DNS resolution (which could itself be slow/fail)
  - More overhead than a raw TCP connect
  - We want to know "is internet available?" not "is Sarvam up?"

Why socket not requests/urllib?
  - socket is Python built-in — no extra pip install
  - We're not fetching data, just testing reachability
  - Faster and lighter than an HTTP request

Tiered fallback chain (wired in Step 4):
  Sarvam API → Claude API → OpenAI API → Ollama (always offline fallback)
"""

import socket

from src.maya.config.settings import settings


class ConnectivityChecker:
    """
    Lightweight internet connectivity checker.

    Usage:
        checker = ConnectivityChecker()
        if checker.is_online():
            # use Sarvam / Claude / OpenAI
        else:
            # use Ollama fallback
    """

    def __init__(self) -> None:
        self.host    = settings.CONNECTIVITY_HOST
        self.port    = settings.CONNECTIVITY_PORT
        self.timeout = settings.CONNECTIVITY_TIMEOUT

    def is_online(self) -> bool:
        """
        Return True if internet is reachable, False otherwise.

        Attempts a TCP connection to self.host:self.port within self.timeout seconds.
        Any exception (timeout, refused, no route) → False (offline).
        MAYA_OFFLINE_MODE=true in .env hard-overrides to always return False.
        """
        if settings.OFFLINE_MODE:
            return False   # Hard override: never go online in offline mode

        try:
            socket.setdefaulttimeout(self.timeout)
            with socket.create_connection((self.host, self.port)):
                return True
        except OSError:
            return False
