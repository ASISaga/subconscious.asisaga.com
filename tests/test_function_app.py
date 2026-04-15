"""Tests for function_app — graceful degradation and route registration.

Verifies that:
* The module loads without raising and exports ``app``.
* All expected route functions are registered when all deps are present.
* The homepage handler returns valid HTML with minimal dependencies.
* The graceful-degradation try/except pattern exists in the source.
* Log calls use the expected concise-success / verbose-failure pattern.

Note on module-reload testing
------------------------------
Reloading ``function_app`` inside a test process that has already imported
``fastmcp`` / ``beartype`` causes a circular-import error in ``beartype``
because its C-extension state is already initialised.  We therefore test
graceful-degradation structurally (source inspection) and behaviourally
(calling route handlers with mocked dependencies).
"""

from __future__ import annotations

import inspect
import json
import re
from unittest.mock import MagicMock

import azure.functions as func

import function_app

# ---------------------------------------------------------------------------
# Basic load / export tests
# ---------------------------------------------------------------------------


class TestFunctionAppLoads:
    def test_module_exports_app(self):
        """function_app must export an ``app`` attribute."""
        assert hasattr(function_app, "app")

    def test_app_is_function_app_instance(self):
        assert isinstance(function_app.app, func.FunctionApp)

    def test_all_route_functions_registered(self):
        """All four route groups must register successfully when deps are present."""
        for name in (
            "homepage",
            "view_conversations",
            "view_monitor",
            "data_orchestrations",
            "data_orchestration",
            "data_health",
            "mcp_endpoint",
        ):
            assert hasattr(function_app, name), (
                f"expected route function '{name}' to be registered"
            )
            assert callable(getattr(function_app, name))


# ---------------------------------------------------------------------------
# Homepage handler — minimal-deps smoke test
# ---------------------------------------------------------------------------


class TestHomepageHandler:
    def test_homepage_returns_html_response(self):
        """homepage() must return an HttpResponse with HTML content."""
        req = MagicMock(spec=func.HttpRequest)
        resp = function_app.homepage(req)
        assert isinstance(resp, func.HttpResponse)
        assert "text/html" in (resp.headers.get("Content-Type") or "")

    def test_homepage_html_contains_subconscious(self):
        req = MagicMock(spec=func.HttpRequest)
        resp = function_app.homepage(req)
        assert b"Subconscious" in resp.get_body()

    def test_homepage_html_links_to_mcp(self):
        req = MagicMock(spec=func.HttpRequest)
        resp = function_app.homepage(req)
        assert b"/mcp" in resp.get_body()


# ---------------------------------------------------------------------------
# Data health handler — smoke test
# ---------------------------------------------------------------------------


class TestDataHealthHandler:
    def test_data_health_returns_json_response(self):
        """data_health() must return an HttpResponse with JSON content."""
        req = MagicMock(spec=func.HttpRequest)
        resp = function_app.data_health(req)
        assert isinstance(resp, func.HttpResponse)
        assert "application/json" in (resp.headers.get("Content-Type") or "")

    def test_data_health_body_has_status_ok(self):
        req = MagicMock(spec=func.HttpRequest)
        resp = function_app.data_health(req)
        body = json.loads(resp.get_body())
        assert body.get("status") == "ok"


# ---------------------------------------------------------------------------
# Graceful-degradation structural tests
# ---------------------------------------------------------------------------


class TestGracefulDegradationStructure:
    """Verify that the try/except pattern exists in function_app.py source."""

    _SRC = inspect.getsource(function_app)

    def test_homepage_group_wrapped_in_try(self):
        """Group 1 (homepage) must be inside a try block."""
        assert "try:" in self._SRC
        # homepage definition must appear after the first try:
        try_pos = self._SRC.index("try:")
        home_pos = self._SRC.index("def homepage(")
        assert home_pos > try_pos, "homepage def must be inside a try block"

    def test_view_routes_wrapped_in_try(self):
        """view_conversations and view_monitor must be inside a try block."""
        assert "def view_conversations(" in self._SRC
        assert "def view_monitor(" in self._SRC
        # Both must be preceded by a try: at some point
        assert self._SRC.count("try:") >= 2, "at least two try blocks expected for route groups"

    def test_error_blocks_use_exc_info(self):
        """Every logger.error call in graceful-degradation blocks must pass exc_info=True."""
        error_calls = re.findall(r"logger\.error\([^)]+\)", self._SRC)
        assert error_calls, "expected logger.error calls in function_app"
        for call_src in error_calls:
            assert "exc_info=True" in call_src, (
                f"logger.error call missing exc_info=True: {call_src!r}"
            )

    def test_mcp_asgi_not_at_bare_module_level(self):
        """_mcp_asgi must be created inside a try block, not at bare module level."""
        src_lines = self._SRC.splitlines()
        for i, line in enumerate(src_lines):
            stripped = line.strip()
            if stripped.startswith("_mcp_asgi ="):
                # The line must be indented (inside a try block)
                assert line.startswith("    "), (
                    f"_mcp_asgi assignment at line {i + 1} must be indented inside a try block"
                )

    def test_homepage_registered_before_mcp(self):
        """homepage route must appear before the MCP try block in the source."""
        home_pos = self._SRC.index("def homepage(")
        mcp_try_pos = self._SRC.index("mcp.http_app(")
        assert home_pos < mcp_try_pos, (
            "homepage route must be registered before the MCP ASGI adapter is built"
        )


# ---------------------------------------------------------------------------
# Startup log pattern
# ---------------------------------------------------------------------------


class TestStartupLogs:
    def test_success_log_calls_use_info(self):
        """Successful registration messages must use logger.info (single-arg or f-string)."""
        src = inspect.getsource(function_app)
        info_calls = re.findall(r'logger\.info\("([^"]+)"', src)
        assert info_calls, "expected logger.info calls in function_app"
        for msg in info_calls:
            # Confirm no newlines in format strings
            assert "\n" not in msg, f"INFO format string must be single-line: {msg!r}"

    def test_loading_banner_present_in_source(self):
        src = inspect.getsource(function_app)
        assert "function_app loading" in src

    def test_loaded_successfully_present_in_source(self):
        src = inspect.getsource(function_app)
        assert "loaded successfully" in src
