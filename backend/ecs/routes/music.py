"""
routes/music.py

Music query endpoint.

Endpoint
────────
  GET /music/query?title=&artist=&year=&album=

At least one query parameter must be provided (per the spec).
Multiple conditions are combined with AND.

The service layer (services/dynamo.py) handles smart index routing:
  - artist provided  → GSI artist-index (Query)
  - title provided   → main table or LSI title-year-index (Query)
  - year/album only  → full-table Scan with FilterExpression

Each result item is enriched with a pre-signed S3 URL for the artist image
before being returned to the frontend.
"""

from flask import Blueprint, request, jsonify

from services.dynamo import query_music
from services.s3     import enrich_with_presigned_url

music_bp = Blueprint("music", __name__)


# ── GET /music/query ───────────────────────────────────────────────────────────
@music_bp.route("/query", methods=["GET"])
def query():
    """
    Query the music table.

    Query parameters (all optional, but at least one required):
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
    title  = (request.args.get("title")  or "").strip() or None
    artist = (request.args.get("artist") or "").strip() or None
    year   = (request.args.get("year")   or "").strip() or None
    album  = (request.args.get("album")  or "").strip() or None

    if not any([title, artist, year, album]):
        return jsonify({"error": "At least one search field must be provided."}), 400

    items = query_music(title=title, artist=artist, year=year, album=album)

    # Attach pre-signed S3 URL to each result
    enriched = [enrich_with_presigned_url(item) for item in items]

    if not enriched:
        return jsonify({
            "results": [],
            "message": "No result is retrieved. Please query again",
        }), 200

    return jsonify({"results": enriched}), 200
