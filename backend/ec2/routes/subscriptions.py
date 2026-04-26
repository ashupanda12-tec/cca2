"""
routes/subscriptions.py

Subscription CRUD endpoints.

The spec requires proper RESTful HTTP methods, so:
  GET    /subscriptions        — list a user's subscriptions
  POST   /subscriptions        — subscribe to a song
  DELETE /subscriptions        — remove a subscription

Each GET response enriches items with a pre-signed S3 URL so the frontend
can display artist images without the backend acting as a media proxy.
"""

from flask import Blueprint, request, jsonify

from services.dynamo import (
    get_subscriptions,
    add_subscription,
    remove_subscription,
)
from services.s3 import enrich_with_presigned_url

subscriptions_bp = Blueprint("subscriptions", __name__)


# ── GET /subscriptions?email=<email> ──────────────────────────────────────────
@subscriptions_bp.route("", methods=["GET"])
def list_subscriptions():
    """
    Return all subscribed songs for the given user.

    Query parameters:
        email — the logged-in user's email address (required)

    Response 200:
        { "subscriptions": [ { email, song_id, title, artist, year,
                                album, image_url, presigned_url }, ... ] }

    Response 400:
        { "error": "email is required." }
    """
    email = (request.args.get("email") or "").strip()
    if not email:
        return jsonify({"error": "email is required."}), 400

    items    = get_subscriptions(email)
    enriched = [enrich_with_presigned_url(item) for item in items]

    return jsonify({"subscriptions": enriched}), 200


# ── POST /subscriptions ────────────────────────────────────────────────────────
@subscriptions_bp.route("", methods=["POST"])
def subscribe():
    """
    Add a song to the user's subscription list.

    Request body (JSON):
        {
            "email":     "...",
            "title":     "...",
            "artist":    "...",
            "year":      "...",
            "album":     "...",
            "image_url": "..."    (raw source URL from the music table)
        }

    Response 201:
        { "message": "Subscribed successfully." }

    Response 400:
        { "error": "..." }
    """
    data = request.get_json(silent=True, force=True) or {}

    email     = (data.get("email")     or "").strip()
    title     = (data.get("title")     or "").strip()
    artist    = (data.get("artist")    or "").strip()
    year      = (data.get("year")      or "").strip()
    album     = (data.get("album")     or "").strip()
    image_url = (data.get("image_url") or "").strip()

    if not all([email, title, artist, year]):
        return jsonify({"error": "email, title, artist, and year are required."}), 400

    add_subscription(
        email=email,
        title=title,
        artist=artist,
        year=year,
        album=album,
        image_url=image_url,
    )

    return jsonify({"message": "Subscribed successfully."}), 201


# ── DELETE /subscriptions ──────────────────────────────────────────────────────
@subscriptions_bp.route("", methods=["DELETE"])
def unsubscribe():
    """
    Remove a song from the user's subscription list.

    Request body (JSON):
        {
            "email":  "...",
            "title":  "...",
            "artist": "...",
            "year":   "..."
        }

    Response 200:
        { "message": "Removed successfully." }

    Response 400:
        { "error": "..." }
    """
    data = request.get_json(silent=True, force=True) or {}

    email  = (data.get("email")  or "").strip()
    title  = (data.get("title")  or "").strip()
    artist = (data.get("artist") or "").strip()
    year   = (data.get("year")   or "").strip()

    if not all([email, title, artist, year]):
        return jsonify({"error": "email, title, artist, and year are required."}), 400

    remove_subscription(email=email, title=title, artist=artist, year=year)

    return jsonify({"message": "Removed successfully."}), 200
