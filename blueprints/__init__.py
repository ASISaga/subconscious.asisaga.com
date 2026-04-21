"""Azure Functions blueprints for the Subconscious MCP server.

Each sub-module defines a :class:`azure.functions.Blueprint` that registers
one semantic group of HTTP routes.  The blueprints are registered with the
main :class:`azure.functions.FunctionApp` in ``function_app.py``.

Sub-modules
-----------
* :mod:`blueprints.homepage` — ``GET /`` landing page.
* :mod:`blueprints.views` — ``GET /view/conversations`` and ``GET /monitor``.
* :mod:`blueprints.data` — ``GET /data/*`` JSON-LD data endpoints.
* :mod:`blueprints.mcp_endpoint` — ``/mcp/{*rest}`` FastMCP proxy.
"""
