import azure.functions as func
import logging

try:
    from subconscious.app import create_app
    subconscious_app = create_app()
except Exception as e:
    logging.error(f"Failed to initialize Subconscious: {e}")
    # Fallback to a tiny Starlette app just to keep the worker alive
    from starlette.applications import Starlette
    subconscious_app = Starlette()

app = func.AsgiFunctionApp(
    app=subconscious_app,
    http_auth_level=func.AuthLevel.ANONYMOUS,
    route="{*route}"
)
