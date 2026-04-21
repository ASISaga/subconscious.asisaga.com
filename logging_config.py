"""Logging configuration for the Subconscious MCP server.

Reads ``LOG_LEVEL`` from the environment (default ``INFO``) and configures
the root logger accordingly.  Set ``LOG_LEVEL=DEBUG`` in Azure Function App
Settings to enable verbose logging for troubleshooting in Azure.

Azure Functions captures Python logging output and forwards it to Application
Insights automatically.  Setting ``LOG_LEVEL=DEBUG`` therefore enables full
request/response traces in Application Insights without any additional setup.
"""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure root logging from the ``LOG_LEVEL`` environment variable.

    Levels accepted: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``.
    Unknown values fall back to ``INFO``.

    Noisy Azure SDK and HTTP library loggers are capped at ``WARNING`` to
    avoid flooding Application Insights with low-value internal traces.
    """
    raw = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, raw, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )

    # Suppress high-volume SDK internals unless explicitly overridden
    for noisy in ("azure.core", "azure.identity", "urllib3", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    logger = logging.getLogger(__name__)
    logger.debug("Logging initialised at level %s", raw)
