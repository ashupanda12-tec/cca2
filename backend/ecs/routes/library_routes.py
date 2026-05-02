"""
routes/library_routes.py

User library management endpoints for the ECS backend.
Identical behaviour to the EC2 version.

  GET    /subscriptions  —  list saved songs
  POST   /subscriptions  —  add a song
  DELETE /subscriptions  —  remove a song
"""

from flask import Blueprint, request, jsonify

from services.db_gateway import (
    retrieve_library,
    save_to_library,
    drop_from_library,
)
from services.storage_helper import attach_image_token

library_bp = Blueprint("library", __name__)


def _read_body() -> dict:
    return request.get_json(silent=True, force=True) or {}


@library_bp.route("", methods=["GET"])
def fetch_saved_songs():
    """
    Return all songs in a user's library.

    Query param: email (required)
    200 →  { "subscriptions": [ { ...fields..., "presigned_url" } ] }
    400 →  { "error": "email is required." }
    """
    account_addr = (request.args.get("email") or "").strip()
    if not account_addr:
        return jsonify({"error": "email is required."}), 400

    raw_rows   = retrieve_library(account_addr)
    final_rows = [attach_image_token(row) for row in raw_rows]

    return jsonify({"subscriptions": final_rows}), 200


@library_bp.route("", methods=["POST"])
def add_to_library():
    """
    Persist a song to the user's library.

    Body: email, title, artist, year (required) + album, image_url (optional)
    201 →  { "message": "Subscribed successfully." }
    400 →  { "error": "..." }
    """
    body = _read_body()

    account_addr = (body.get("email")     or "").strip()
    track_name   = (body.get("title")     or "").strip()
    performer    = (body.get("artist")    or "").strip()
    release_year = (body.get("year")      or "").strip()
    collection   = (body.get("album")     or "").strip()
    raw_img      = (body.get("image_url") or "").strip()

    if not all([account_addr, track_name, performer, release_year]):
        return jsonify({"error": "email, title, artist, and year are required."}), 400

    save_to_library(
        email=account_addr,
        title=track_name,
        artist=performer,
        year=release_year,
        album=collection,
        image_url=raw_img,
    )

    return jsonify({"message": "Subscribed successfully."}), 201


@library_bp.route("", methods=["DELETE"])
def remove_from_library():
    """
    Remove a song from the user's library.

    Body: email, title, artist, year (all required)
    200 →  { "message": "Removed successfully." }
    400 →  { "error": "..." }
    """
    body = _read_body()

    account_addr = (body.get("email")  or "").strip()
    track_name   = (body.get("title")  or "").strip()
    performer    = (body.get("artist") or "").strip()
    release_year = (body.get("year")   or "").strip()

    if not all([account_addr, track_name, performer, release_year]):
        return jsonify({"error": "email, title, artist, and year are required."}), 400

    drop_from_library(
        email=account_addr,
        title=track_name,
        artist=performer,
        year=release_year,
    )

    return jsonify({"message": "Removed successfully."}), 200
