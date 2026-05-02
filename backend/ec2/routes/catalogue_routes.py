"""
routes/catalogue_routes.py

Exposes the song-search endpoint.

Endpoint
────────
  GET /music/query?title=&artist=&year=&album=

Caller must supply at least one non-empty query parameter.
All supplied parameters are combined with AND semantics — only songs that
match every provided field are returned.

Index routing (handled in services/db_gateway.py):
  • performer name present  →  GSI query on performer-index
  • track name only          →  main-table or LSI query
  • year / collection only  →  full-table scan with FilterExpression

Every result is enriched with a time-limited S3 URL before the response is
sent, so the frontend can render artist images without hitting a public bucket.
"""

from flask import Blueprint, request, jsonify

from services.db_gateway     import search_catalogue
from services.storage_helper import attach_image_token

catalogue_bp = Blueprint("catalogue", __name__)


# ── GET /music/query ───────────────────────────────────────────────────────────

@catalogue_bp.route("/query", methods=["GET"])
def find_tracks():
    """
    Search the song catalogue.

    Query-string parameters (all optional, ≥1 required):
        title  — partial or full track title
        artist — performer / band name
        year   — four-digit release year (stored as String)
        album  — album / collection name

    Response 200  →  { "results": [ { ...song fields..., "presigned_url": "..." } ] }
    Response 400  →  { "error": "At least one search field must be provided." }
    Response 200 (empty)  →  { "results": [], "message": "No result is retrieved. Please query again" }
    """
    track_name    = (request.args.get("title")  or "").strip() or None
    performer     = (request.args.get("artist") or "").strip() or None
    release_year  = (request.args.get("year")   or "").strip() or None
    collection    = (request.args.get("album")  or "").strip() or None

    if not any([track_name, performer, release_year, collection]):
        return jsonify({"error": "At least one search field must be provided."}), 400

    hits = search_catalogue(
        title=track_name,
        artist=performer,
        year=release_year,
        album=collection,
    )

    enriched_hits = [attach_image_token(row) for row in hits]

    if not enriched_hits:
        return jsonify({
            "results": [],
            "message": "No result is retrieved. Please query again",
        }), 200

    return jsonify({"results": enriched_hits}), 200
