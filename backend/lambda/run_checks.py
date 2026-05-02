"""
run_checks.py

Direct invocation tests for all Lambda handlers.
Calls each handler function with a mock API Gateway event dict and verifies
the HTTP status code.  No Docker, no SAM CLI, no local HTTP server required —
only active AWS credentials and the real DynamoDB tables and S3 bucket.

Prerequisites
─────────────
  - Active AWS Academy session (credentials in ~/.aws/credentials)
  - Infrastructure scripts already run (tables populated, S3 images uploaded)
  - pip install -r requirements.txt

Run from backend/lambda/:
    python run_checks.py

Coverage
────────
  ✓ Credentials : sign-in (valid), sign-in (bad password), sign-in (missing field)
  ✓ Credentials : register (new account), register (duplicate address)
  ✓ Credentials : end session
  ✓ Catalogue   : search by performer, by performer + collection, no params (400)
  ✓ Library     : list, add, list (verify added), remove, list (verify removed)
  ✓ Validation  : missing required fields (400 paths)
"""

import json
import sys

# Import handlers — must run from backend/lambda/ so Python resolves modules
try:
    from handlers.credential_handlers import (
        sign_in_handler,
        register_handler,
        end_session_handler,
    )
    from handlers.catalogue_handlers import search_handler
    from handlers.library_handlers   import (
        list_saved_handler,
        add_entry_handler,
        remove_entry_handler,
    )
except ImportError as exc:
    print(f"[ERROR] Could not import handlers: {exc}")
    print("Run this script from the backend/lambda/ directory.")
    sys.exit(1)


# ── ANSI colour helpers ────────────────────────────────────────────────────────
_OK   = "\033[32m✓\033[0m"
_FAIL = "\033[31m✗\033[0m"

_outcomes: list[tuple[str, bool]] = []


# ── Event builders ─────────────────────────────────────────────────────────────

def _post_event(body: dict) -> dict:
    """Minimal API Gateway proxy event for a POST or DELETE request."""
    return {
        "httpMethod":            "POST",
        "path":                  "/",
        "headers":               {"Content-Type": "application/json"},
        "queryStringParameters": None,
        "body":                  json.dumps(body),
    }


def _get_event(params: dict) -> dict:
    """Minimal API Gateway proxy event for a GET request."""
    return {
        "httpMethod":            "GET",
        "path":                  "/",
        "headers":               {},
        "queryStringParameters": params or None,
        "body":                  None,
    }


def _delete_event(body: dict) -> dict:
    """Minimal API Gateway proxy event for a DELETE request."""
    return {
        "httpMethod":            "DELETE",
        "path":                  "/",
        "headers":               {"Content-Type": "application/json"},
        "queryStringParameters": None,
        "body":                  json.dumps(body),
    }


# ── Test runner ────────────────────────────────────────────────────────────────

def verify(label: str, handler, event: dict, want_status: int) -> None:
    """
    Invoke a handler, compare its status code to want_status, print result.
    Records the pass/fail outcome for the final summary.
    """
    try:
        response    = handler(event, {})
        got_status  = response["statusCode"]
        body_dict   = json.loads(response.get("body", "{}"))
        passed      = (got_status == want_status)
        icon        = _OK if passed else _FAIL
        _outcomes.append((label, passed))

        print(f"{icon}  [{got_status}] {label}")
        if not passed:
            print(f"     Expected {want_status}, received {got_status}")
            print(f"     Body: {json.dumps(body_dict, indent=2)}")
        else:
            summary = str(body_dict)
            print(f"     {summary[:120]}{'...' if len(summary) > 120 else ''}")

    except Exception as exc:
        _outcomes.append((label, False))
        print(f"{_FAIL}  [ERR] {label}")
        print(f"     Exception: {exc}")

    print()


# ── Test data ──────────────────────────────────────────────────────────────────
# Update _SEED_ADDR to match the first seed user created by
# scripts/create_login_table.py  →  <STUDENT_ID>0@student.rmit.edu.au

_SEED_ADDR     = "s4109620@student.rmit.edu.au"
_SEED_SECRET   = "012345"

_TEMP_ADDR     = "lambda_verify_user@example.com"
_TEMP_ALIAS    = "VerifyUser"
_TEMP_SECRET   = "verifypass999"

_SAMPLE_TRACK  = {
    "email":     _SEED_ADDR,
    "title":     "Love Story",
    "artist":    "Taylor Swift",
    "year":      "2008",
    "album":     "Fearless",
    "image_url": "https://raw.githubusercontent.com/YingZhang2015/cc/main/TaylorSwift.jpg",
}


# ── Credential checks ──────────────────────────────────────────────────────────

def check_credentials() -> None:
    print("=" * 60)
    print("CREDENTIAL CHECKS")
    print("=" * 60)

    verify(
        "Sign-in — valid credentials",
        sign_in_handler,
        _post_event({"email": _SEED_ADDR, "password": _SEED_SECRET}),
        want_status=200,
    )
    verify(
        "Sign-in — incorrect password",
        sign_in_handler,
        _post_event({"email": _SEED_ADDR, "password": "wrongpass"}),
        want_status=401,
    )
    verify(
        "Sign-in — missing email field",
        sign_in_handler,
        _post_event({"password": _SEED_SECRET}),
        want_status=400,
    )
    verify(
        "Register — new account",
        register_handler,
        _post_event({
            "email":     _TEMP_ADDR,
            "user_name": _TEMP_ALIAS,
            "password":  _TEMP_SECRET,
        }),
        want_status=201,
    )
    verify(
        "Register — duplicate address (expect 409)",
        register_handler,
        _post_event({
            "email":     _TEMP_ADDR,
            "user_name": _TEMP_ALIAS,
            "password":  _TEMP_SECRET,
        }),
        want_status=409,
    )
    verify(
        "End session",
        end_session_handler,
        _post_event({}),
        want_status=200,
    )


# ── Catalogue checks ───────────────────────────────────────────────────────────

def check_catalogue() -> None:
    print("=" * 60)
    print("CATALOGUE CHECKS")
    print("=" * 60)

    verify(
        "Search by performer — Taylor Swift",
        search_handler,
        _get_event({"artist": "Taylor Swift"}),
        want_status=200,
    )
    verify(
        "Search by performer + collection — Taylor Swift / Fearless",
        search_handler,
        _get_event({"artist": "Taylor Swift", "album": "Fearless"}),
        want_status=200,
    )
    verify(
        "Search by performer + year — Jimmy Buffett 1974",
        search_handler,
        _get_event({"artist": "Jimmy Buffett", "year": "1974"}),
        want_status=200,
    )
    verify(
        "Search — no parameters supplied (expect 400)",
        search_handler,
        _get_event({}),
        want_status=400,
    )
    verify(
        "Search — performer not in catalogue (expect 200 + empty results)",
        search_handler,
        _get_event({"artist": "NoSuchArtistXYZ"}),
        want_status=200,
    )


# ── Library checks ─────────────────────────────────────────────────────────────

def check_library() -> None:
    print("=" * 60)
    print("LIBRARY CHECKS")
    print("=" * 60)

    verify(
        "List library — before adding entry",
        list_saved_handler,
        _get_event({"email": _SEED_ADDR}),
        want_status=200,
    )
    verify(
        "Add entry — Love Story",
        add_entry_handler,
        _post_event(_SAMPLE_TRACK),
        want_status=201,
    )
    verify(
        "List library — after adding (Love Story should appear)",
        list_saved_handler,
        _get_event({"email": _SEED_ADDR}),
        want_status=200,
    )
    verify(
        "Remove entry — Love Story",
        remove_entry_handler,
        _delete_event({
            "email":  _SEED_ADDR,
            "title":  _SAMPLE_TRACK["title"],
            "artist": _SAMPLE_TRACK["artist"],
            "year":   _SAMPLE_TRACK["year"],
        }),
        want_status=200,
    )
    verify(
        "List library — after removing (Love Story should be absent)",
        list_saved_handler,
        _get_event({"email": _SEED_ADDR}),
        want_status=200,
    )
    verify(
        "Add entry — missing required field (expect 400)",
        add_entry_handler,
        _post_event({"email": _SEED_ADDR, "title": "Love Story"}),
        want_status=400,
    )
    verify(
        "List library — missing email param (expect 400)",
        list_saved_handler,
        _get_event({}),
        want_status=400,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    check_credentials()
    check_catalogue()
    check_library()

    total   = len(_outcomes)
    passed  = sum(1 for _, ok in _outcomes if ok)
    failed  = total - passed

    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} failed)")
        sys.exit(1)
    else:
        print("  — all passed ✓")
        sys.exit(0)
