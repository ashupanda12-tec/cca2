"""
handlers/subscriptions.py

Lambda handlers for subscription CRUD endpoints.

  list_handler      → GET    /subscriptions?email=<email>
  subscribe_handler → POST   /subscriptions
  unsubscribe_handler → DELETE /subscriptions

Each GET response enriches items with a pre-signed S3 URL so the frontend
can display artist images without the backend acting as a media proxy.
"""

import json

from services.dynamo import (
    get_subscriptions,
    add_subscription,
    remove_subscription,
)
from services.s3 import enrich_with_presigned_url

# ── Shared helpers ─────────────────────────────────────────────────────────────

_CORS_HEADERS = {
    "Content-Type":                "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,DELETE",
}


def _resp(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers":    _CORS_HEADERS,
        "body":       json.dumps(body),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


# ── GET /subscriptions?email=<email> ──────────────────────────────────────────

def list_handler(event, context):
    """
    Return all subscribed songs for the given user.

    Query string parameters:
        email — the logged-in user's email address (required)

    Response 200:
        { "subscriptions": [ { email, song_id, title, artist, year,
                                album, image_url, presigned_url }, ... ] }

    Response 400:
        { "error": "email is required." }
    """
    qs    = event.get("queryStringParameters") or {}
    email = (qs.get("email") or "").strip()

    if not email:
        return _resp(400, {"error": "email is required."})

    items    = get_subscriptions(email)
    enriched = [enrich_with_presigned_url(item) for item in items]

    return _resp(200, {"subscriptions": enriched})


# ── POST /subscriptions ────────────────────────────────────────────────────────

def subscribe_handler(event, context):
    """
    Add a song to the user's subscription list.

    Request body (JSON):
        {
            "email":     "...",
            "title":     "...",
            "artist":    "...",
            "year":      "...",
            "album":     "...",
            "image_url": "..."
        }

    Response 201: { "message": "Subscribed successfully." }
    Response 400: { "error": "..." }
    """
    data = _parse_body(event)

    email     = (data.get("email")     or "").strip()
    title     = (data.get("title")     or "").strip()
    artist    = (data.get("artist")    or "").strip()
    year      = (data.get("year")      or "").strip()
    album     = (data.get("album")     or "").strip()
    image_url = (data.get("image_url") or "").strip()

    if not all([email, title, artist, year]):
        return _resp(400, {"error": "email, title, artist, and year are required."})

    add_subscription(
        email=email,
        title=title,
        artist=artist,
        year=year,
        album=album,
        image_url=image_url,
    )

    return _resp(201, {"message": "Subscribed successfully."})


# ── DELETE /subscriptions ──────────────────────────────────────────────────────

def unsubscribe_handler(event, context):
    """
    Remove a song from the user's subscription list.

    Request body (JSON):
        { "email": "...", "title": "...", "artist": "...", "year": "..." }

    Response 200: { "message": "Removed successfully." }
    Response 400: { "error": "..." }
    """
    data = _parse_body(event)

    email  = (data.get("email")  or "").strip()
    title  = (data.get("title")  or "").strip()
    artist = (data.get("artist") or "").strip()
    year   = (data.get("year")   or "").strip()

    if not all([email, title, artist, year]):
        return _resp(400, {"error": "email, title, artist, and year are required."})

    remove_subscription(email=email, title=title, artist=artist, year=year)

    return _resp(200, {"message": "Removed successfully."})
