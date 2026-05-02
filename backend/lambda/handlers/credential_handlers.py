"""
handlers/credential_handlers.py

Lambda entry points for user-identity operations.

  sign_in_handler   → POST /auth/login
  register_handler  → POST /auth/register
  end_session_handler → POST /auth/logout

Each function follows the API Gateway Lambda Proxy Integration contract:
  Input  — event dict with httpMethod, path, headers, queryStringParameters, body
  Output — dict with statusCode (int), headers (dict), body (JSON string)

CORS headers are added to every response so that a browser frontend served
from a different origin can consume this API without being blocked.
"""

import json
from botocore.exceptions import ClientError

from services.db_gateway import fetch_account, insert_account

# ── Shared response infrastructure ────────────────────────────────────────────

_ACCESS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,DELETE",
}


def _make_response(http_status: int, payload: dict) -> dict:
    """Wrap a dict into the API Gateway proxy response envelope."""
    return {
        "statusCode": http_status,
        "headers":    _ACCESS_HEADERS,
        "body":       json.dumps(payload),
    }


def _decode_body(event: dict) -> dict:
    """
    Safely parse the JSON body string from an API Gateway event.
    Returns an empty dict if the body is absent or malformed.
    """
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


# ── POST /auth/login ───────────────────────────────────────────────────────────

def sign_in_handler(event: dict, context) -> dict:
    """
    Authenticate a user against the accounts table.

    Body  →  { "email": "...", "password": "..." }
    200   →  { "email": "...", "user_name": "..." }
    400   →  { "error": "Email and password are required." }
    401   →  { "error": "email or password is invalid" }
    """
    body    = _decode_body(event)
    addr    = (body.get("email")    or "").strip()
    secret  = (body.get("password") or "").strip()

    if not addr or not secret:
        return _make_response(400, {"error": "Email and password are required."})

    record = fetch_account(addr)

    if record is None or record.get("password") != secret:
        return _make_response(401, {"error": "email or password is invalid"})

    return _make_response(200, {
        "email":     record["email"],
        "user_name": record["user_name"],
    })


# ── POST /auth/register ────────────────────────────────────────────────────────

def register_handler(event: dict, context) -> dict:
    """
    Create a new user account.

    Body  →  { "email": "...", "user_name": "...", "password": "..." }
    201   →  { "message": "Registration successful." }
    400   →  { "error": "..." }
    409   →  { "error": "The email already exists" }
    """
    body    = _decode_body(event)
    addr    = (body.get("email")     or "").strip()
    alias   = (body.get("user_name") or "").strip()
    secret  = (body.get("password")  or "").strip()

    if not addr or not alias or not secret:
        return _make_response(400, {"error": "Email, username, and password are required."})

    pre_existing = fetch_account(addr)
    if pre_existing is not None:
        return _make_response(409, {"error": "The email already exists"})

    try:
        insert_account(addr, alias, secret)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _make_response(409, {"error": "The email already exists"})
        raise

    return _make_response(201, {"message": "Registration successful."})


# ── POST /auth/logout ──────────────────────────────────────────────────────────

def end_session_handler(event: dict, context) -> dict:
    """
    Stateless logout acknowledgement — no server-side state to clean up.
    200  →  { "message": "Logged out successfully." }
    """
    return _make_response(200, {"message": "Logged out successfully."})
