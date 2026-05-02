"""
test_local.py

Direct handler invocation tests — no Docker, no SAM, no infrastructure needed.

Each test calls the Lambda handler function directly with a mock API Gateway
event dict and prints the HTTP status code + response body.

Requirements:
  - Active AWS credentials (AWS Academy Lab session)
  - pip install -r requirements.txt

Run from backend/lambda/:
    python test_local.py

The tests run against the real DynamoDB tables and S3 bucket, so make sure
the infrastructure setup scripts have been run first.

Test coverage:
  ✓ Auth:          login (valid), login (bad password), login (missing fields)
  ✓ Auth:          register (new user), register (duplicate email)
  ✓ Auth:          logout
  ✓ Music:         query by artist, query by artist+album, no params (expect 400)
  ✓ Subscriptions: list, subscribe, list (verify added), unsubscribe, list (verify removed)
"""

import json
import sys

# ── Import handlers (must run from backend/lambda/ so Python finds the modules)
try:
    from handlers.auth          import login_handler, register_handler, logout_handler
    from handlers.music         import query_handler
    from handlers.subscriptions import list_handler, subscribe_handler, unsubscribe_handler
except ImportError as e:
    print(f"[ERROR] Could not import handlers: {e}")
    print("Make sure you run this script from the backend/lambda/ directory.")
    sys.exit(1)


# ── Helpers ────────────────────────────────────────────────────────────────────

_PASS = "\033[32m✓\033[0m"
_FAIL = "\033[31m✗\033[0m"
_results: list[tuple[str, bool]] = []


def _make_post_event(body: dict) -> dict:
    """Minimal API Gateway proxy event for a POST request."""
    return {
        "httpMethod":            "POST",
        "path":                  "/",
        "headers":               {"Content-Type": "application/json"},
        "queryStringParameters": None,
        "body":                  json.dumps(body),
    }


def _make_get_event(params: dict) -> dict:
    """Minimal API Gateway proxy event for a GET request."""
    return {
        "httpMethod":            "GET",
        "path":                  "/",
        "headers":               {},
        "queryStringParameters": params,
        "body":                  None,
    }


def _make_delete_event(body: dict) -> dict:
    """Minimal API Gateway proxy event for a DELETE request."""
    return {
        "httpMethod":            "DELETE",
        "path":                  "/",
        "headers":               {"Content-Type": "application/json"},
        "queryStringParameters": None,
        "body":                  json.dumps(body),
    }


def run_test(name: str, handler, event: dict, expected_status: int):
    """
    Invoke a Lambda handler and print the result.
    Prints PASS if the status code matches expected_status, FAIL otherwise.
    """
    try:
        response = handler(event, {})
        status   = response["statusCode"]
        body     = json.loads(response.get("body", "{}"))
        ok       = (status == expected_status)
        icon     = _PASS if ok else _FAIL
        _results.append((name, ok))
        print(f"{icon}  [{status}] {name}")
        if not ok:
            print(f"     Expected status {expected_status}, got {status}")
            print(f"     Body: {json.dumps(body, indent=2)}")
        else:
            # Print a short summary of the response for visibility
            brief = str(body)[:120] + ("..." if len(str(body)) > 120 else "")
            print(f"     {brief}")
    except Exception as exc:
        _results.append((name, False))
        print(f"\033[31m✗\033[0m  [ERR] {name}")
        print(f"     Exception: {exc}")
    print()


# ── Test data ──────────────────────────────────────────────────────────────────
# Update _SEED_EMAIL to match the first seed user created by
# scripts/create_login_table.py — i.e. <STUDENT_ID>0@student.rmit.edu.au

_SEED_EMAIL    = "s41096200@student.rmit.edu.au"   # update to your seed user email
_SEED_PASSWORD = "012345"
_TEST_EMAIL    = "lambda_test_user@example.com"
_TEST_USERNAME = "LambdaTestUser"
_TEST_PASSWORD = "testpass123"

_SONG = {
    "email":     _SEED_EMAIL,
    "title":     "Love Story",
    "artist":    "Taylor Swift",
    "year":      "2008",
    "album":     "Fearless",
    "image_url": "https://rmit.instructure.com/courses/158468/files/38463305/download?verifier=TaylorSwift",
}


# ── Auth tests ─────────────────────────────────────────────────────────────────

def test_auth():
    print("=" * 60)
    print("AUTH TESTS")
    print("=" * 60)

    run_test(
        "Login — valid credentials",
        login_handler,
        _make_post_event({"email": _SEED_EMAIL, "password": _SEED_PASSWORD}),
        expected_status=200,
    )
    run_test(
        "Login — wrong password",
        login_handler,
        _make_post_event({"email": _SEED_EMAIL, "password": "wrongpassword"}),
        expected_status=401,
    )
    run_test(
        "Login — missing email field",
        login_handler,
        _make_post_event({"password": _SEED_PASSWORD}),
        expected_status=400,
    )
    run_test(
        "Register — new user",
        register_handler,
        _make_post_event({
            "email":     _TEST_EMAIL,
            "user_name": _TEST_USERNAME,
            "password":  _TEST_PASSWORD,
        }),
        expected_status=201,
    )
    run_test(
        "Register — duplicate email (expect 409)",
        register_handler,
        _make_post_event({
            "email":     _TEST_EMAIL,
            "user_name": _TEST_USERNAME,
            "password":  _TEST_PASSWORD,
        }),
        expected_status=409,
    )
    run_test(
        "Logout",
        logout_handler,
        _make_post_event({}),
        expected_status=200,
    )


# ── Music tests ────────────────────────────────────────────────────────────────

def test_music():
    print("=" * 60)
    print("MUSIC TESTS")
    print("=" * 60)

    run_test(
        "Query by artist — Taylor Swift",
        query_handler,
        _make_get_event({"artist": "Taylor Swift"}),
        expected_status=200,
    )
    run_test(
        "Query by artist + album — Taylor Swift / Fearless",
        query_handler,
        _make_get_event({"artist": "Taylor Swift", "album": "Fearless"}),
        expected_status=200,
    )
    run_test(
        "Query by artist + year — Jimmy Buffett 1974",
        query_handler,
        _make_get_event({"artist": "Jimmy Buffett", "year": "1974"}),
        expected_status=200,
    )
    run_test(
        "Query — no params (expect 400)",
        query_handler,
        _make_get_event({}),
        expected_status=400,
    )
    run_test(
        "Query — non-existent artist (expect 200 + empty results)",
        query_handler,
        _make_get_event({"artist": "This Artist Does Not Exist"}),
        expected_status=200,
    )


# ── Subscriptions tests ────────────────────────────────────────────────────────

def test_subscriptions():
    print("=" * 60)
    print("SUBSCRIPTIONS TESTS")
    print("=" * 60)

    run_test(
        "List subscriptions — before subscribe",
        list_handler,
        _make_get_event({"email": _SEED_EMAIL}),
        expected_status=200,
    )
    run_test(
        "Subscribe to Love Story",
        subscribe_handler,
        _make_post_event(_SONG),
        expected_status=201,
    )
    run_test(
        "List subscriptions — after subscribe (Love Story should appear)",
        list_handler,
        _make_get_event({"email": _SEED_EMAIL}),
        expected_status=200,
    )
    run_test(
        "Unsubscribe from Love Story",
        unsubscribe_handler,
        _make_delete_event({
            "email":  _SEED_EMAIL,
            "title":  _SONG["title"],
            "artist": _SONG["artist"],
            "year":   _SONG["year"],
        }),
        expected_status=200,
    )
    run_test(
        "List subscriptions — after unsubscribe (Love Story should be gone)",
        list_handler,
        _make_get_event({"email": _SEED_EMAIL}),
        expected_status=200,
    )
    run_test(
        "Subscribe — missing required field (expect 400)",
        subscribe_handler,
        _make_post_event({"email": _SEED_EMAIL, "title": "Love Story"}),
        expected_status=400,
    )
    run_test(
        "List — missing email (expect 400)",
        list_handler,
        _make_get_event({}),
        expected_status=400,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_auth()
    test_music()
    test_subscriptions()

    # Summary
    total  = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    failed = total - passed

    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} failed)")
        sys.exit(1)
    else:
        print("  — all passed ✓")
        sys.exit(0)
