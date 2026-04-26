"""
routes/auth.py

Authentication endpoints: login, register, logout.

Design notes
────────────
This backend is stateless — no server-side session is maintained between
requests.  On a successful login the server returns the user's email and
user_name; the frontend stores these (e.g. in memory or a cookie) and
passes the email in the body of every subsequent authenticated request.

This keeps the API clean and avoids cross-origin cookie issues when the
frontend is hosted on a different origin (e.g. S3 static site).

Endpoints
─────────
  POST /auth/login
  POST /auth/register
  POST /auth/logout
"""

from flask import Blueprint, request, jsonify
from botocore.exceptions import ClientError

from services.dynamo import get_user, create_user

auth_bp = Blueprint("auth", __name__)


# ── POST /auth/login ───────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Validate user credentials against the login table.

    Request body (JSON):
        { "email": "...", "password": "..." }

    Responses:
        200 { "email": "...", "user_name": "..." }   — success
        400 { "error": "..." }                       — missing fields
        401 { "error": "email or password is invalid" }
    """
    # force=True makes Flask parse the body as JSON even if the Content-Type
    # header is missing or wrong — handles curl/Postman quirks gracefully.
    data = request.get_json(silent=True, force=True) or {}
    email    = (data.get("email")    or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = get_user(email)

    if user is None or user.get("password") != password:
        return jsonify({"error": "email or password is invalid"}), 401

    return jsonify({
        "email":     user["email"],
        "user_name": user["user_name"],
    }), 200


# ── POST /auth/register ────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.

    Checks for email uniqueness then writes to the login table.

    Request body (JSON):
        { "email": "...", "user_name": "...", "password": "..." }

    Responses:
        201 { "message": "Registration successful." }
        400 { "error": "..." }         — missing or invalid fields
        409 { "error": "The email already exists" }
    """
    data = request.get_json(silent=True, force=True) or {}
    email     = (data.get("email")     or "").strip()
    user_name = (data.get("user_name") or "").strip()
    password  = (data.get("password")  or "").strip()

    if not email or not user_name or not password:
        return jsonify({"error": "Email, username, and password are required."}), 400

    # Check uniqueness first with a point-read (cheaper than a conditional write
    # that fails on conflict, and gives a cleaner error message)
    existing = get_user(email)
    if existing is not None:
        return jsonify({"error": "The email already exists"}), 409

    try:
        create_user(email, user_name, password)
    except ClientError as e:
        # ConditionExpression failed — race condition where two registrations
        # with the same email arrived simultaneously
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return jsonify({"error": "The email already exists"}), 409
        raise

    return jsonify({"message": "Registration successful."}), 201


# ── POST /auth/logout ──────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Stateless logout — the server has no session to invalidate, so this
    endpoint simply acknowledges the request.  The frontend is responsible
    for discarding the stored email/user_name and redirecting to the login page.

    Response:
        200 { "message": "Logged out successfully." }
    """
    return jsonify({"message": "Logged out successfully."}), 200
