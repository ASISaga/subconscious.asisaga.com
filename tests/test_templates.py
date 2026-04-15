"""Tests for subconscious.templates — HTML5/CSS3 page templates."""

from __future__ import annotations

from subconscious.templates import conversations_page, monitor_page


class TestConversationsPage:
    """Verify the conversations SPA HTML structure."""

    def test_is_valid_html5(self):
        html = conversations_page()
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "</html>" in html

    def test_has_viewport_meta(self):
        html = conversations_page()
        assert "viewport" in html

    def test_fetches_orchestrations_endpoint(self):
        html = conversations_page()
        assert "/data/orchestrations" in html

    def test_uses_vanilla_fetch_api(self):
        html = conversations_page()
        assert "fetch(" in html
        assert "react" not in html.lower()
        assert "jquery" not in html.lower()

    def test_renders_schema_org_action(self):
        html = conversations_page()
        assert "orchestration_id" in html
        assert "actionStatus" in html

    def test_renders_schema_org_message(self):
        html = conversations_page()
        assert "msg-bubble" in html
        assert "agent_id" in html
        assert "sender" in html

    def test_status_filter_ui(self):
        html = conversations_page()
        assert "status-filter" in html
        assert "active" in html
        assert "completed" in html

    def test_links_to_monitor(self):
        html = conversations_page()
        assert "/monitor" in html

    def test_has_jsonld_provenance_strip(self):
        html = conversations_page()
        assert "jsonld-strip" in html

    def test_has_loading_indicator(self):
        html = conversations_page()
        assert "loading-bar" in html

    def test_auto_refresh_for_active(self):
        html = conversations_page()
        assert "setInterval" in html

    def test_uses_css_custom_properties(self):
        html = conversations_page()
        assert "--bg:" in html
        assert "--accent:" in html
        assert "var(--" in html

    def test_semantic_html5_elements(self):
        html = conversations_page()
        assert "<header" in html
        assert "<aside" in html
        assert "<main" in html
        assert "<article" in html

    def test_url_state_management(self):
        html = conversations_page()
        assert "history.pushState" in html
        assert "URLSearchParams" in html


class TestMonitorPage:
    """Verify the monitor page HTML structure."""

    def test_is_valid_html5(self):
        html = monitor_page()
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "</html>" in html

    def test_polls_health_endpoint(self):
        html = monitor_page()
        assert "/data/health" in html

    def test_uses_vanilla_fetch_api(self):
        html = monitor_page()
        assert "fetch(" in html
        assert "react" not in html.lower()

    def test_has_status_cards(self):
        html = monitor_page()
        assert "Azure Functions" in html
        assert "FastMCP" in html
        assert "Azure Table Storage" in html
        assert "Demo Data" in html

    def test_links_to_conversations_browser(self):
        html = monitor_page()
        assert "/view/conversations" in html

    def test_links_to_mcp_endpoint(self):
        html = monitor_page()
        assert "/mcp" in html

    def test_links_to_health_data_feed(self):
        html = monitor_page()
        assert "/data/orchestrations" in html

    def test_has_endpoint_reference_table(self):
        html = monitor_page()
        assert "/data/health" in html

    def test_has_mcp_tools_reference(self):
        html = monitor_page()
        assert "show_conversations" in html
        assert "create_orchestration" in html
        assert "summarize_conversation" in html

    def test_auto_refresh_30s(self):
        html = monitor_page()
        assert "30000" in html

    def test_uses_css_custom_properties(self):
        html = monitor_page()
        assert "--bg:" in html
        assert "var(--" in html
