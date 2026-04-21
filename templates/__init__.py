"""HTML template loader for the Subconscious web UI.

Provides :func:`get_app_html`, :func:`conversations_page`, and
:func:`monitor_page` by reading the corresponding ``.html`` files in this
directory at import time.  No HTML is embedded in Python source.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """Read and return the contents of an HTML file in this directory."""
    return (_DIR / filename).read_text(encoding="utf-8")


def get_app_html() -> str:
    """Return the Subconscious landing page HTML."""
    return _load("app.html")


def conversations_page() -> str:
    """Return the Conversations SPA HTML.

    The page fetches ``/data/orchestrations`` on load and renders the
    Schema.org Action JSON-LD list as a two-panel UI (sidebar + conversation
    thread).  Selecting an orchestration fetches
    ``/data/orchestrations/{id}`` and renders the nested Conversation +
    Message JSON-LD entirely on the client side.
    """
    return _load("conversations.html")


def monitor_page() -> str:
    """Return the static Monitor page HTML.

    The page polls ``/data/health`` every 30 seconds and displays the
    status of Azure Functions, FastMCP, Azure Table Storage, and demo data.
    """
    return _load("monitor.html")
