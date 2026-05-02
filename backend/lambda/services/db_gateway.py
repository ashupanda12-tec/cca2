"""
services/db_gateway.py

All DynamoDB interactions for the Lambda backend.
Identical logic to the EC2 / ECS service layers — the compute layer
(Flask vs Lambda handlers) is the only difference.

Module-level table references are created once per cold start and reused
across warm invocations, eliminating repeated connection setup overhead.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import settings

_db = boto3.resource("dynamodb", region_name=settings.CLOUD_REGION)

_users_tbl     = _db.Table(settings.USERS_TABLE)
_catalogue_tbl = _db.Table(settings.CATALOGUE_TABLE)
_library_tbl   = _db.Table(settings.LIBRARY_TABLE)


# ── Account operations ─────────────────────────────────────────────────────────

def fetch_account(addr: str) -> dict | None:
    """Point-read a user record by email.  Returns None if absent."""
    outcome = _users_tbl.get_item(Key={"email": addr})
    return outcome.get("Item")


def insert_account(addr: str, display_name: str, secret: str) -> None:
    """
    Write a new user record.
    Raises ClientError(ConditionalCheckFailedException) if addr already exists.
    """
    _users_tbl.put_item(
        Item={
            "email":     addr,
            "user_name": display_name,
            "password":  secret,
        },
        ConditionExpression="attribute_not_exists(email)",
    )


# ── Catalogue operations ───────────────────────────────────────────────────────

def _combine_filters(conditions: list):
    """AND-fold a list of Attr conditions.  Returns None for an empty list."""
    if not conditions:
        return None
    combined = conditions[0]
    for extra in conditions[1:]:
        combined = combined & extra
    return combined


def search_catalogue(
    title:  str | None = None,
    artist: str | None = None,
    year:   str | None = None,
    album:  str | None = None,
) -> list[dict]:
    """
    Smart-route a search across the catalogue table.

    Routing:
      performer present → GSI query  (artist-index)
      track only        → main table or LSI query  (title-year-index)
      year/album only   → full table scan with FilterExpression
    """
    # Route A: GSI by performer
    if artist:
        key_expr = Key("artist").eq(artist)
        if year:
            key_expr = key_expr & Key("year").eq(year)

        supplemental = []
        if title:
            supplemental.append(Attr("title").eq(title))
        if album:
            supplemental.append(Attr("album").eq(album))

        call_kwargs: dict = {
            "IndexName":              settings.PERFORMER_GSI,
            "KeyConditionExpression": key_expr,
        }
        extra = _combine_filters(supplemental)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        return _catalogue_tbl.query(**call_kwargs).get("Items", [])

    # Route B: main table or LSI by track name
    if title:
        key_expr = Key("title").eq(title)

        supplemental = []
        if album:
            supplemental.append(Attr("album").eq(album))

        if year:
            key_expr = key_expr & Key("year").eq(year)
            call_kwargs = {
                "IndexName":              settings.TRACK_LSI,
                "KeyConditionExpression": key_expr,
            }
        else:
            call_kwargs = {"KeyConditionExpression": key_expr}

        extra = _combine_filters(supplemental)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        return _catalogue_tbl.query(**call_kwargs).get("Items", [])

    # Route C: scan with year/album filters
    scan_conds = []
    if year:
        scan_conds.append(Attr("year").eq(year))
    if album:
        scan_conds.append(Attr("album").eq(album))

    call_kwargs = {}
    extra = _combine_filters(scan_conds)
    if extra is not None:
        call_kwargs["FilterExpression"] = extra

    return _catalogue_tbl.scan(**call_kwargs).get("Items", [])


# ── Library operations ─────────────────────────────────────────────────────────

def _compose_entry_id(track: str, performer: str, yr: str) -> str:
    """Build the composite sort key stored in the library table."""
    return f"{track}#{performer}#{yr}"


def retrieve_library(addr: str) -> list[dict]:
    """Fetch all library entries for an account.  Single Query — no scan."""
    outcome = _library_tbl.query(
        KeyConditionExpression=Key("email").eq(addr)
    )
    return outcome.get("Items", [])


def save_to_library(
    email: str, title: str, artist: str,
    year: str, album: str, image_url: str,
) -> None:
    """Persist a library entry.  Idempotent on duplicate calls."""
    entry_id = _compose_entry_id(title, artist, year)
    _library_tbl.put_item(
        Item={
            "email":     email,
            "song_id":   entry_id,
            "title":     title,
            "artist":    artist,
            "year":      year,
            "album":     album,
            "image_url": image_url,
        }
    )


def drop_from_library(email: str, title: str, artist: str, year: str) -> None:
    """Remove a library entry by its exact composite key.  No-op if absent."""
    entry_id = _compose_entry_id(title, artist, year)
    _library_tbl.delete_item(
        Key={"email": email, "song_id": entry_id}
    )
