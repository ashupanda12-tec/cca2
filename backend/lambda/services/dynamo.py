"""
services/dynamo.py

All DynamoDB operations for the Lambda backend.

Identical to the EC2 backend's services/dynamo.py — the business logic is
the same regardless of compute layer.  Only the entry-point (Flask vs Lambda
handler) differs between the two implementations.

Query routing strategy
──────────────────────
The music table uses title (PK) + artist#year (SK), with:
  - GSI  artist-index      → artist (PK) + year (SK)
  - LSI  title-year-index  → title  (PK) + year (SK)

Query logic (all filters are AND-combined per the spec):

  1. artist provided  → Query on GSI artist-index.
                        If year is also provided, add it to KeyCondition.
                        Remaining filters (title, album) go in FilterExpression.

  2. title provided, no artist
                      → Query on main table PK.
                        If year is also provided, use LSI title-year-index.
                        Remaining filter (album) goes in FilterExpression.

  3. only album and/or year (no artist, no title)
                      → Scan with FilterExpression.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import config

# ── DynamoDB resource ──────────────────────────────────────────────────────────
_dynamodb = boto3.resource("dynamodb", region_name=config.REGION)

login_table         = _dynamodb.Table(config.LOGIN_TABLE)
music_table         = _dynamodb.Table(config.MUSIC_TABLE)
subscriptions_table = _dynamodb.Table(config.SUBSCRIPTIONS_TABLE)


# ══════════════════════════════════════════════════════════════════════════════
# Login table operations
# ══════════════════════════════════════════════════════════════════════════════

def get_user(email: str) -> dict | None:
    """
    Fetch a single user from the login table by email (PK).
    Returns the item dict, or None if not found.
    """
    response = login_table.get_item(Key={"email": email})
    return response.get("Item")


def create_user(email: str, user_name: str, password: str) -> None:
    """
    Insert a new user into the login table.
    Raises ClientError(ConditionalCheckFailedException) if email already exists.
    """
    login_table.put_item(
        Item={
            "email":     email,
            "user_name": user_name,
            "password":  password,
        },
        ConditionExpression="attribute_not_exists(email)",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Music table operations
# ══════════════════════════════════════════════════════════════════════════════

def _build_filter_expr(conditions: list):
    """AND-combine a list of Attr conditions.  Returns None if empty."""
    if not conditions:
        return None
    expr = conditions[0]
    for cond in conditions[1:]:
        expr = expr & cond
    return expr


def query_music(
    title:  str | None = None,
    artist: str | None = None,
    year:   str | None = None,
    album:  str | None = None,
) -> list[dict]:
    """
    Query or scan the music table based on provided filters.
    At least one filter must be non-empty (validated at the handler layer).
    All conditions are combined with AND.
    """

    # ── Case 1: artist provided → use GSI artist-index ────────────────────────
    if artist:
        key_cond = Key("artist").eq(artist)
        if year:
            key_cond = key_cond & Key("year").eq(year)

        extra_filters = []
        if title:
            extra_filters.append(Attr("title").eq(title))
        if album:
            extra_filters.append(Attr("album").eq(album))

        kwargs: dict = {
            "IndexName":              config.ARTIST_GSI,
            "KeyConditionExpression": key_cond,
        }
        filter_expr = _build_filter_expr(extra_filters)
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr

        response = music_table.query(**kwargs)
        return response.get("Items", [])

    # ── Case 2: title provided (no artist) → use main table or LSI ────────────
    if title:
        key_cond = Key("title").eq(title)

        extra_filters = []
        if album:
            extra_filters.append(Attr("album").eq(album))

        if year:
            key_cond = key_cond & Key("year").eq(year)
            kwargs = {
                "IndexName":              config.TITLE_LSI,
                "KeyConditionExpression": key_cond,
            }
        else:
            kwargs = {"KeyConditionExpression": key_cond}

        filter_expr = _build_filter_expr(extra_filters)
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr

        response = music_table.query(**kwargs)
        return response.get("Items", [])

    # ── Case 3: only album and/or year → Scan ─────────────────────────────────
    scan_filters = []
    if year:
        scan_filters.append(Attr("year").eq(year))
    if album:
        scan_filters.append(Attr("album").eq(album))

    kwargs = {}
    filter_expr = _build_filter_expr(scan_filters)
    if filter_expr is not None:
        kwargs["FilterExpression"] = filter_expr

    response = music_table.scan(**kwargs)
    return response.get("Items", [])


# ══════════════════════════════════════════════════════════════════════════════
# Subscriptions table operations
# ══════════════════════════════════════════════════════════════════════════════

def _make_song_id(title: str, artist: str, year: str) -> str:
    """Build the composite sort key used in the subscriptions table."""
    return f"{title}#{artist}#{year}"


def get_subscriptions(email: str) -> list[dict]:
    """
    Return all subscriptions for a given user.
    Query on PK (email) — O(subscriptions), not a Scan.
    """
    response = subscriptions_table.query(
        KeyConditionExpression=Key("email").eq(email)
    )
    return response.get("Items", [])


def add_subscription(
    email:     str,
    title:     str,
    artist:    str,
    year:      str,
    album:     str,
    image_url: str,
) -> None:
    """
    Add a song to the user's subscriptions.
    Idempotent: subscribing to the same song twice is a no-op.
    """
    song_id = _make_song_id(title, artist, year)
    subscriptions_table.put_item(
        Item={
            "email":     email,
            "song_id":   song_id,
            "title":     title,
            "artist":    artist,
            "year":      year,
            "album":     album,
            "image_url": image_url,
        }
    )


def remove_subscription(email: str, title: str, artist: str, year: str) -> None:
    """
    Remove a specific subscription by its full primary key.
    No-op if the item does not exist.
    """
    song_id = _make_song_id(title, artist, year)
    subscriptions_table.delete_item(
        Key={
            "email":   email,
            "song_id": song_id,
        }
    )
