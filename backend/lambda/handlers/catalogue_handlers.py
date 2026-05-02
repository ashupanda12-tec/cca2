"""
handlers/catalogue_handlers.py

Lambda entry point for the song-search endpoint.

  search_handler → GET /music/query?title=&artist=&year=&album=

At least one query-string parameter must be non-empty.
All supplied parameters are AND-combined in the service layer.
Results are enriched with time-limited S3 image URLs before returning.
"""

import json

from services.db_gateway     import search_catalogue
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


# ── GET /music/query ───────────────────────────────────────────────────────────

def search_handler(event: dict, context) -> dict:
    """
    Query the song catalogue.

    Query-string parameters (≥1 required):
        title, artist, year, album

    200 (results)  →  { "results": [ { ...fields..., "presigned_url" } ] }
    200 (empty)    →  { "results": [], "message": "No result is retrieved. Please query again" }
    400            →  { "error": "At least one search field must be provided." }
    """
    qs           = event.get("queryStringParameters") or {}
    track_name   = (qs.get("title")  or "").strip() or None
    performer    = (qs.get("artist") or "").strip() or None
    release_year = (qs.get("year")   or "").strip() or None
    collection   = (qs.get("album")  or "").strip() or None

    if not any([track_name, performer, release_year, collection]):
        return _make_response(400, {"error": "At least one search field must be provided."})

    hits = search_catalogue(
        title=track_name,
        artist=performer,
        year=release_year,
        album=collection,
    )
    enriched_hits = [attach_image_token(row) for row in hits]

    if not enriched_hits:
        return _make_response(200, {
            "results": [],
            "message": "No result is retrieved. Please query again",
        })

    return _make_response(200, {"results": enriched_hits})
