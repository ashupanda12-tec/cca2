"""
handlers/music.py

Lambda handler for the music query endpoint.

  query_handler → GET /music/query?title=&artist=&year=&album=

At least one query parameter must be supplied (per the spec).
Multiple conditions are AND-combined in the service layer.

The service layer handles smart index routing:
  - artist provided  → GSI artist-index (Query)
  - title provided   → main table or LSI title-year-index (Query)
  - year/album only  → full-table Scan with FilterExpression

Each result is enriched with a pre-signed S3 URL before being returned.
"""

import json

from services.dynamo import query_music
from services.s3     import enrich_with_presigned_url

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


# ── GET /music/query ───────────────────────────────────────────────────────────

def query_handler(event, context):
    """
    Query the music table.

    Query string parameters (all optional, but at least one required):
        title  — song title
        artist — artist name
        year   — release year (stored as String in DynamoDB)
        album  — album name

    Response 200:
        { "results": [ { title, artist, year, album, image_url,
                          presigned_url, "artist#year" }, ... ] }

    Response 400:
        { "error": "At least one search field must be provided." }

    Response 200 (no matches):
        { "results": [], "message": "No result is retrieved. Please query again" }
    """
    # API Gateway puts query params in event['queryStringParameters'], which
    # may be None if no params were supplied.
    qs     = event.get("queryStringParameters") or {}
    title  = (qs.get("title")  or "").strip() or None
    artist = (qs.get("artist") or "").strip() or None
    year   = (qs.get("year")   or "").strip() or None
    album  = (qs.get("album")  or "").strip() or None

    if not any([title, artist, year, album]):
        return _resp(400, {"error": "At least one search field must be provided."})

    items    = query_music(title=title, artist=artist, year=year, album=album)
    enriched = [enrich_with_presigned_url(item) for item in items]

    if not enriched:
        return _resp(200, {
            "results": [],
            "message": "No result is retrieved. Please query again",
        })

    return _resp(200, {"results": enriched})
