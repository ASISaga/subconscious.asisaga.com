# This single HTTP-trigger function handles all JSON-RPC 2.0 methods over SSE.
import azure.functions as func
import json
import uuid
from jsonrpcserver import method, dispatch
from linkedinmcp.linkedinapi import (
    postonlinkedin, search_members,
    senddirectmessage, fetchprofilestats,
    fetch_feed
)

# Define JSON-RPC methods
@method
def createpost(content: str, mediaurn: str = None):
    return postonlinkedin(content, media_urn)

@method
def create_article(title: str, body: str):
    # For articles, LinkedIn uses a different endpoint—stubbed here
    return {"articleId": "dummy-article-id"}

@method
def upload_media(url: str):
    # Stub—actual media upload requires multipart/form-data
    return {"mediaUrn": "urn:li:digitalmediaAsset:XYZ"}

@method
def search_people(keywords: str, location: str = None, limit: int = 25):
    return search_members(keywords, location, limit)

@method
def send_message(recipient: str, text: str, inmail: bool = False):
    return senddirectmessage(recipient, text, inmail)

@method
def getprofilestats():
    return fetchprofilestats()

@method
def getfeedposts(limit: int = 10):
    return fetch_feed(limit)

# SSE helper
def sse_stream(responses):
    for resp in responses:
        # prefix with JSON-RPC envelope if dispatch didn’t
        data = resp if isinstance(resp, str) else json.dumps(resp)
        yield f"data: {data}\n\n"

# Azure Function entrypoint
async def main(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body().decode()
    # dispatch returns one or more JSON-RPC responses
    responses = dispatch(body, debug=False)
    # Prepare SSE response
    return func.HttpResponse(
        sse_stream(responses),
        status_code=200,
        mimetype="text/event-stream"
    )