"""
routes/credential_routes.py

Identity management endpoints for the ECS backend.
Functionally identical to the EC2 version — only the import paths differ.

Routes
──────
  POST /auth/login     —  verify credentials
  POST /auth/register  —  open a new account
  POST /auth/logout    —  acknowledge session closure (stateless)
"""

from flask import Blueprint, request, jsonify
from botocore.exceptions import ClientError

from services.db_gateway import fetch_account, insert_account

credential_bp = Blueprint("credentials", __name__)


def _extract_json() -> dict:
    return request.get_json(silent=True, force=True) or {}


@credential_bp.route("/login", methods=["POST"])
def sign_in():
    """
    Validate email + password against the accounts table.

    Body      →  { "email": "...", "password": "..." }
    200 OK    →  { "email": "...", "user_name": "..." }
    400       →  { "error": "..." }
    401       →  { "error": "email or password is invalid" }
    """
    payload  = _extract_json()
    addr     = (payload.get("email")    or "").strip()
    secret   = (payload.get("password") or "").strip()

    if not addr or not secret:
        return jsonify({"error": "Email and password are required."}), 400

    record = fetch_account(addr)

    if record is None or record.get("password") != secret:
        return jsonify({"error": "email or password is invalid"}), 401

    return jsonify({
        "email":     record["email"],
        "user_name": record["user_name"],
    }), 200


@credential_bp.route("/register", methods=["POST"])
def create_account():
    """
    Create a new user account.

    Body      →  { "email": "...", "user_name": "...", "password": "..." }
    201       →  { "message": "Registration successful." }
    400       →  { "error": "..." }
    409       →  { "error": "The email already exists" }
    """
    payload   = _extract_json()
    addr      = (payload.get("email")     or "").strip()
    alias     = (payload.get("user_name") or "").strip()
    secret    = (payload.get("password")  or "").strip()

    if not addr or not alias or not secret:
        return jsonify({"error": "Email, username, and password are required."}), 400

    pre_existing = fetch_account(addr)
    if pre_existing is not None:
        return jsonify({"error": "The email already exists"}), 409

    try:
        insert_account(addr, alias, secret)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return jsonify({"error": "The email already exists"}), 409
        raise

    return jsonify({"message": "Registration successful."}), 201


@credential_bp.route("/logout", methods=["POST"])
def close_session():
    """
    No-op logout acknowledgement.
    Response 200  →  { "message": "Logged out successfully." }
    """
    return jsonify({"message": "Logged out successfully."}), 200
