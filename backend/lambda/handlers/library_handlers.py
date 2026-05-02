"""
handlers/library_handlers.py

Lambda entry points for user library (subscription) operations.

  list_saved_handler    → GET    /subscriptions?email=<addr>
  add_entry_handler     → POST   /subscriptions
  remove_entry_handler  → DELETE /subscriptions

GET responses include time-limited S3 image URLs so the frontend
can display artist artwork without direct public bucket access.
"""

import json

from services.db_gateway import (
    retrieve_library,
    save_to_library,
    drop_from_library,
)
from services.storage_helper import attach_image_token

_ACCESS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,DELETE",
}


def _make_response(http_status: int, payload: dict) -> dict:
    return {
        "statusCode": http_status,
        "headers":    _ACCESS_HEADERS,
        "body":       json.dumps(payload),
    }


def _decode_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


# ── GET /subscriptions?email=<addr> ───────────────────────────────────────────

def list_saved_handler(event: dict, context) -> dict:
    """
    Return every song in a user's library.

    Query param: email (required)
    200  →  { "subscriptions": [ { ...fields..., "presigned_url" } ] }
    400  →  { "error": "email is required." }
    """
    qs           = event.get("queryStringParameters") or {}
    account_addr = (qs.get("email") or "").strip()

    if not account_addr:
        return _make_response(400, {"error": "email is required."})

    raw_rows   = retrieve_library(account_addr)
    final_rows = [attach_image_token(row) for row in raw_rows]

    return _make_response(200, {"subscriptions": final_rows})


# ── POST /subscriptions ────────────────────────────────────────────────────────

def add_entry_handler(event: dict, context) -> dict:
    """
    Add a song to the user's library.

    Body (required): email, title, artist, year
    Body (optional): album, image_url
    201  →  { "message": "Subscribed successfully." }
    400  →  { "error": "..." }
    """
    body         = _decode_body(event)
    account_addr = (body.get("email")     or "").strip()
    track_name   = (body.get("title")     or "").strip()
    performer    = (body.get("artist")    or "").strip()
    release_year = (body.get("year")      or "").strip()
    collection   = (body.get("album")     or "").strip()
    raw_img      = (body.get("image_url") or "").strip()

    if not all([account_addr, track_name, performer, release_year]):
        return _make_response(400, {"error": "email, title, artist, and year are required."})

    save_to_library(
        email=account_addr,
        title=track_name,
        artist=performer,
        year=release_year,
        album=collection,
        image_url=raw_img,
    )

    return _make_response(201, {"message": "Subscribed successfully."})


# ── DELETE /subscriptions ──────────────────────────────────────────────────────

def remove_entry_handler(event: dict, context) -> dict:
    """
    Remove a song from the user's library using its composite identity.

    Body: email, title, artist, year (all required)
    200  →  { "message": "Removed successfully." }
    400  →  { "error": "..." }
    """
    body         = _decode_body(event)
    account_addr = (body.get("email")  or "").strip()
    track_name   = (body.get("title")  or "").strip()
    performer    = (body.get("artist") or "").strip()
    release_year = (body.get("year")   or "").strip()

    if not all([account_addr, track_name, performer, release_year]):
        return _make_response(400, {"error": "email, title, artist, and year are required."})

    drop_from_library(
        email=account_addr,
        title=track_name,
        artist=performer,
        year=release_year,
    )

    return _make_response(200, {"message": "Removed successfully."})
