"""
routes/catalogue_routes.py

Song-search endpoint for the ECS backend.
Identical behaviour to the EC2 version.

  GET /music/query?title=&artist=&year=&album=
"""

from flask import Blueprint, request, jsonify

from services.db_gateway     import search_catalogue
from services.storage_helper import attach_image_token

catalogue_bp = Blueprint("catalogue", __name__)


@catalogue_bp.route("/query", methods=["GET"])
def find_tracks():
    """
    Search the catalogue with AND-combined filters.

    Params:   title, artist, year, album  (≥1 required)
    200 OK →  { "results": [ { ...song fields..., "presigned_url" } ] }
    400    →  { "error": "At least one search field must be provided." }
    200 (empty) → { "results": [], "message": "No result is retrieved. Please query again" }
    """
    track_name   = (request.args.get("title")  or "").strip() or None
    performer    = (request.args.get("artist") or "").strip() or None
    release_year = (request.args.get("year")   or "").strip() or None
    collection   = (request.args.get("album")  or "").strip() or None

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
