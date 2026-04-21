"""Tests for function_app — blueprint registration and route handler smoke tests.

Verifies that:
* The module loads without raising and exports ``app``.
* All blueprint modules load and export a ``bp`` attribute.
* Expected route handler functions are defined in each blueprint.
* Route handlers return correct response types.
* Graceful-degradation try/except pattern exists in function_app source.
* Log calls use the expected concise-success / verbose-failure pattern.
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


# ---------------------------------------------------------------------------
# Blueprint registration tests
# ---------------------------------------------------------------------------


class TestBlueprintRegistration:
    """All blueprints must be importable and export a ``bp`` Blueprint."""

    def test_homepage_blueprint_exports_bp(self):
        from blueprints.homepage import bp
        assert isinstance(bp, func.Blueprint)

    def test_views_blueprint_exports_bp(self):
        from blueprints.views import bp
        assert isinstance(bp, func.Blueprint)

    def test_data_blueprint_exports_bp(self):
        from blueprints.data import bp
        assert isinstance(bp, func.Blueprint)

    def test_mcp_endpoint_blueprint_exports_bp(self):
        from blueprints.mcp_endpoint import bp
        assert isinstance(bp, func.Blueprint)

    def test_homepage_blueprint_has_route_handler(self):
        from blueprints import homepage
        assert hasattr(homepage, "homepage")
        assert callable(homepage.homepage)

    def test_views_blueprint_has_route_handlers(self):
        from blueprints import views
        assert hasattr(views, "view_conversations")
        assert callable(views.view_conversations)
        assert hasattr(views, "view_monitor")
        assert callable(views.view_monitor)

    def test_data_blueprint_has_route_handlers(self):
        from blueprints import data
        assert hasattr(data, "data_orchestrations")
        assert callable(data.data_orchestrations)
        assert hasattr(data, "data_orchestration")
        assert callable(data.data_orchestration)
        assert hasattr(data, "data_health")
        assert callable(data.data_health)

    def test_mcp_endpoint_blueprint_has_route_handler(self):
        from blueprints import mcp_endpoint
        assert hasattr(mcp_endpoint, "mcp_endpoint")
        assert callable(mcp_endpoint.mcp_endpoint)


# ---------------------------------------------------------------------------
# Homepage handler — smoke test
# ---------------------------------------------------------------------------


class TestHomepageHandler:
    def test_homepage_returns_html_response(self):
        """homepage() must return an HttpResponse with HTML content."""
        from blueprints.homepage import homepage
        req = MagicMock(spec=func.HttpRequest)
        resp = homepage(req)
        assert isinstance(resp, func.HttpResponse)
        assert "text/html" in (resp.headers.get("Content-Type") or "")

    def test_homepage_html_contains_subconscious(self):
        from blueprints.homepage import homepage
        req = MagicMock(spec=func.HttpRequest)
        resp = homepage(req)
        assert b"Subconscious" in resp.get_body()

    def test_homepage_html_links_to_mcp(self):
        from blueprints.homepage import homepage
        req = MagicMock(spec=func.HttpRequest)
        resp = homepage(req)
        assert b"/mcp" in resp.get_body()


# ---------------------------------------------------------------------------
# Data health handler — smoke test
# ---------------------------------------------------------------------------


class TestDataHealthHandler:
    def test_data_health_returns_json_response(self):
        """data_health() must return an HttpResponse with JSON content."""
        from blueprints.data import data_health
        req = MagicMock(spec=func.HttpRequest)
        resp = data_health(req)
        assert isinstance(resp, func.HttpResponse)
        assert "application/json" in (resp.headers.get("Content-Type") or "")

    def test_data_health_body_has_status_ok(self):
        from blueprints.data import data_health
        req = MagicMock(spec=func.HttpRequest)
        resp = data_health(req)
        body = json.loads(resp.get_body())
        assert body.get("status") == "ok"


# ---------------------------------------------------------------------------
# Graceful-degradation structural tests
# ---------------------------------------------------------------------------


class TestGracefulDegradationStructure:
    """Verify that the try/except blueprint-registration pattern exists in function_app.py."""

    _SRC = inspect.getsource(function_app)

    def test_function_app_uses_blueprint_registration(self):
        """function_app must use register_functions to register blueprints."""
        assert "register_functions" in self._SRC

    def test_blueprints_wrapped_in_try(self):
        """Each blueprint registration must be inside a try block."""
        assert self._SRC.count("try:") >= 4, "expected at least 4 try blocks (one per blueprint)"

    def test_error_blocks_use_exc_info(self):
        """Every logger.error call must pass exc_info=True."""
        error_calls = re.findall(r"logger\.error\([^)]+\)", self._SRC)
        assert error_calls, "expected logger.error calls in function_app"
        for call_src in error_calls:
            assert "exc_info=True" in call_src, (
                f"logger.error call missing exc_info=True: {call_src!r}"
            )

    def test_homepage_blueprint_registered_before_mcp(self):
        """Homepage blueprint import must appear before mcp_endpoint blueprint import."""
        home_pos = self._SRC.index("blueprints.homepage")
        mcp_pos = self._SRC.index("blueprints.mcp_endpoint")
        assert home_pos < mcp_pos, (
            "homepage blueprint must be registered before mcp_endpoint blueprint"
        )


# ---------------------------------------------------------------------------
# Startup log pattern
# ---------------------------------------------------------------------------


class TestStartupLogs:
    def test_success_log_calls_use_info(self):
        """Successful registration messages must use logger.info."""
        src = inspect.getsource(function_app)
        info_calls = re.findall(r'logger\.info\("([^"]+)"', src)
        assert info_calls, "expected logger.info calls in function_app"
        for msg in info_calls:
            assert "\n" not in msg, f"INFO format string must be single-line: {msg!r}"

    def test_loading_banner_present_in_source(self):
        src = inspect.getsource(function_app)
        assert "function_app loading" in src

    def test_loaded_successfully_present_in_source(self):
        src = inspect.getsource(function_app)
        assert "loaded successfully" in src

