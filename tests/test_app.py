"""Tests for subconscious.app — landing page HTML."""

from __future__ import annotations

from subconscious.app import get_app_html


class TestAppHtml:
    def test_app_html_exists(self):
        html = get_app_html()
        assert isinstance(html, str)
        assert len(html) > 0

    def test_app_html_is_valid_html(self):
        html = get_app_html()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_app_html_mentions_mcp_endpoint(self):
        html = get_app_html()
        assert "/mcp" in html

    def test_app_html_references_show_conversations_tool(self):
        html = get_app_html()
        assert "show_conversations" in html

    def test_app_html_mentions_subconscious(self):
        html = get_app_html()
        assert "Subconscious" in html
