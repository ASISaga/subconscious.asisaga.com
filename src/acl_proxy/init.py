import os
import fnmatch
import urllib.parse
import requests
import azure.functions as func

# Load ACL and MCP settings from environment
OWNER          = os.getenv("MCP_OWNER")
REPO           = os.getenv("MCP_REPO")
TOKEN          = os.getenv("GITHUB_MCP_PAT")
READ_ONLY      = os.getenv("ACL_READ_ONLY", "").split(",")
READ_WRITE     = os.getenv("ACL_READ_WRITE", "").split(",")
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/v1"

def is_allowed(filepath: str, mode: str) -> bool:
    """
    mode == "read"  → allow if in READ_ONLY or READ_WRITE
    mode == "write" → allow if in READ_WRITE only
    """
    if mode == "read":
        patterns = READ_ONLY + READ_WRITE
    else:
        patterns = READ_WRITE

    return any(fnmatch.fnmatch(filepath, pat) for pat in patterns)

def main(req: func.HttpRequest) -> func.HttpResponse:
    rest = req.route_params.get("rest", "")
    prefix = f"repos/{OWNER}/{REPO}/contents/"
    if not rest.startswith(prefix):
        return func.HttpResponse(
            "Invalid MCP path",
            status_code=400
        )

    # Extract the file path within the repo
    filepath = rest[len(prefix):]
    method   = req.method.upper()
    mode     = "read" if method == "GET" else "write"

    # Enforce ACL
    if not is_allowed(filepath, mode):
        return func.HttpResponse(
            f"{mode.title()} access denied for '{filepath}'",
            status_code=403
        )

    # Rebuild target URL & query params
    query = urllib.parse.urlencode(req.params) or ""
    target_url = f"{GITHUB_MCP_URL}/{rest}{'?' + query if query else ''}"

    # Prepare headers for proxy (override Authorization)
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        **{k: v for k, v in req.headers.items()
           if k.lower() not in ("host", "authorization")}
    }

    # Forward the request
    try:
        resp = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            data=req.get_body(),
            timeout=30
        )
    except requests.RequestException as e:
        return func.HttpResponse(f"Bad Gateway: {e}", status_code=502)

    # Return proxied response
    return func.HttpResponse(
        body=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items()}
    )