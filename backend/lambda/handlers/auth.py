"""
handlers/auth.py

Lambda handlers for authentication endpoints.

  login_handler    → POST /auth/login
  register_handler → POST /auth/register
  logout_handler   → POST /auth/logout

Each function follows the API Gateway Lambda proxy integration contract:
  - Input:  event dict with 'body' (JSON string), 'httpMethod', 'path', etc.
  - Output: dict with 'statusCode', 'headers', and 'body' (JSON string).

CORS headers are returned on every response so the S3-hosted frontend
(a different origin) can call this API from the browser.
"""

import json
from botocore.exceptions import ClientError

from services.dynamo import get_user, create_user

# ── Shared helpers ─────────────────────────────────────────────────────────────

_CORS_HEADERS = {
    "Content-Type":                "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,GET,POST,DELETE",
}


def _resp(status_code: int, body: dict) -> dict:
    """Wrap a dict body into an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers":    _CORS_HEADERS,
        "body":       json.dumps(body),
    }


def _parse_body(event: dict) -> dict:
    """Safely parse the JSON body from an API Gateway event."""
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


# ── POST /auth/login ───────────────────────────────────────────────────────────

def login_handler(event, context):
    """
    Validate user credentials against the login table.

    Request body (JSON):
        { "email": "...", "password": "..." }

    Responses:
        200 { "email": "...", "user_name": "..." }
        400 { "error": "..." }          — missing fields
        401 { "error": "email or password is invalid" }
    """
    data     = _parse_body(event)
    email    = (data.get("email")    or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return _resp(400, {"error": "Email and password are required."})

    user = get_user(email)

    if user is None or user.get("password") != password:
        return _resp(401, {"error": "email or password is invalid"})

    return _resp(200, {
        "email":     user["email"],
        "user_name": user["user_name"],
    })


# ── POST /auth/register ────────────────────────────────────────────────────────

def register_handler(event, context):
    """
    Register a new user.

    Request body (JSON):
        { "email": "...", "user_name": "...", "password": "..." }

    Responses:
        201 { "message": "Registration successful." }
        400 { "error": "..." }          — missing/invalid fields
        409 { "error": "The email already exists" }
    """
    data      = _parse_body(event)
    email     = (data.get("email")     or "").strip()
    user_name = (data.get("user_name") or "").strip()
    password  = (data.get("password")  or "").strip()

    if not email or not user_name or not password:
        return _resp(400, {"error": "Email, username, and password are required."})

    # Point-read to check uniqueness before writing
    existing = get_user(email)
    if existing is not None:
        return _resp(409, {"error": "The email already exists"})

    try:
        create_user(email, user_name, password)
    except ClientError as e:
        # Race condition: two concurrent registrations with the same email
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _resp(409, {"error": "The email already exists"})
        raise

    return _resp(201, {"message": "Registration successful."})


# ── POST /auth/logout ──────────────────────────────────────────────────────────

def logout_handler(event, context):
    """
    Stateless logout — no server-side session to invalidate.
    The frontend is responsible for clearing stored credentials.

    Response:
        200 { "message": "Logged out successfully." }
    """
    return _resp(200, {"message": "Logged out successfully."})
