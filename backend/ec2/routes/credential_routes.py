"""
routes/credential_routes.py

Endpoints that deal with user identity: signing in, creating an account,
and closing a session.

Architecture note
─────────────────
The service is intentionally session-less. No cookie, JWT, or server-side
token is issued. After a successful sign-in the caller receives the account's
email and display name; subsequent requests that need identity (e.g. listing
saved songs) carry the email directly in the request payload. This sidesteps
cross-origin cookie mechanics when the frontend sits on a different domain.

Routes exposed
──────────────
  POST /auth/login
  POST /auth/register
  POST /auth/logout
"""

from flask import Blueprint, request, jsonify
from botocore.exceptions import ClientError

from services.db_gateway import fetch_account, insert_account

credential_bp = Blueprint("credentials", __name__)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _extract_json() -> dict:
    """
    Parse the request body as JSON regardless of Content-Type header.
    Returns an empty dict on failure so callers can safely .get() fields.
    """
    return request.get_json(silent=True, force=True) or {}


# ── POST /auth/login ───────────────────────────────────────────────────────────

@credential_bp.route("/login", methods=["POST"])
def sign_in():
    """
    Verify an existing account's credentials.

    Expected payload  →  { "email": "...", "password": "..." }
    Success  200      →  { "email": "...", "user_name": "..." }
    Bad input 400     →  { "error": "..." }
    Bad creds 401     →  { "error": "email or password is invalid" }
    """
    payload       = _extract_json()
    addr          = (payload.get("email")    or "").strip()
    secret        = (payload.get("password") or "").strip()

    if not addr or not secret:
        return jsonify({"error": "Email and password are required."}), 400

    record = fetch_account(addr)

    if record is None or record.get("password") != secret:
        return jsonify({"error": "email or password is invalid"}), 401

    return jsonify({
        "email":     record["email"],
        "user_name": record["user_name"],
    }), 200


# ── POST /auth/register ────────────────────────────────────────────────────────

@credential_bp.route("/register", methods=["POST"])
def create_account():
    """
    Register a new user in the accounts table.

    Expected payload  →  { "email": "...", "user_name": "...", "password": "..." }
    Success  201      →  { "message": "Registration successful." }
    Bad input 400     →  { "error": "..." }
    Duplicate 409     →  { "error": "The email already exists" }
    """
    payload    = _extract_json()
    addr       = (payload.get("email")     or "").strip()
    alias      = (payload.get("user_name") or "").strip()
    secret     = (payload.get("password")  or "").strip()

    if not addr or not alias or not secret:
        return jsonify({"error": "Email, username, and password are required."}), 400

    # Cheap read-before-write to surface a clean error message.
    # The conditional PutItem below handles the actual race-condition guard.
    pre_existing = fetch_account(addr)
    if pre_existing is not None:
        return jsonify({"error": "The email already exists"}), 409

    try:
        insert_account(addr, alias, secret)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Two concurrent registrations with the same address
            return jsonify({"error": "The email already exists"}), 409
        raise

    return jsonify({"message": "Registration successful."}), 201


# ── POST /auth/logout ──────────────────────────────────────────────────────────

@credential_bp.route("/logout", methods=["POST"])
def close_session():
    """
    Acknowledge a logout request.

    Because the backend holds no session state, this endpoint is a no-op —
    the client is responsible for discarding locally cached identity data.

    Response 200  →  { "message": "Logged out successfully." }
    """
    return jsonify({"message": "Logged out successfully."}), 200
