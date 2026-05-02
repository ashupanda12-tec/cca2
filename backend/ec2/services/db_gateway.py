"""
services/db_gateway.py

All database interactions for the music subscription service.

Index routing decision tree
────────────────────────────
The catalogue table schema is:
  Primary key  →  track_name (PK)  +  performer#release_year (SK)
  GSI          →  performer-index  :  performer (PK)  +  release_year (SK)
  LSI          →  title-year-index :  track_name (PK) +  release_year (SK)

Routing logic (conditions evaluated top-to-bottom, first match wins):

  performer present
      → Query the GSI (performer-index).
        Add release_year to KeyCondition if supplied.
        Put track_name / collection into FilterExpression.

  track_name present, performer absent
      → Query the main table (PK) or the LSI if release_year is also given.
        collection goes into FilterExpression.

  only release_year / collection supplied
      → Full Scan with FilterExpression.
        Necessary because no viable index entry point exists.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import settings

# ── Initialise the DynamoDB resource once per worker process ───────────────────
_db = boto3.resource("dynamodb", region_name=settings.CLOUD_REGION)

_users_tbl    = _db.Table(settings.USERS_TABLE)
_catalogue_tbl = _db.Table(settings.CATALOGUE_TABLE)
_library_tbl   = _db.Table(settings.LIBRARY_TABLE)


# ══════════════════════════════════════════════════════════════════════════════
# Account operations
# ══════════════════════════════════════════════════════════════════════════════

def fetch_account(addr: str) -> dict | None:
    """
    Retrieve a single user record by email address.
    Returns the item dict or None when the address is not registered.
    """
    outcome = _users_tbl.get_item(Key={"email": addr})
    return outcome.get("Item")


def insert_account(addr: str, display_name: str, secret: str) -> None:
    """
    Write a new user record, guarded by an existence check.
    Raises ClientError(ConditionalCheckFailedException) when addr is taken.
    """
    _users_tbl.put_item(
        Item={
            "email":     addr,
            "user_name": display_name,
            "password":  secret,
        },
        ConditionExpression="attribute_not_exists(email)",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Catalogue operations
# ══════════════════════════════════════════════════════════════════════════════

def _combine_filters(conditions: list):
    """
    AND-fold a list of Attr filter conditions into one expression.
    Returns None when the list is empty.
    """
    if not conditions:
        return None
    combined = conditions[0]
    for additional in conditions[1:]:
        combined = combined & additional
    return combined


def search_catalogue(
    title:  str | None = None,
    artist: str | None = None,
    year:   str | None = None,
    album:  str | None = None,
) -> list[dict]:
    """
    Query or scan the catalogue table.
    At least one argument must be truthy (enforced at the route layer).
    All truthy arguments are combined with AND.
    """

    # ── Branch A: performer name present → GSI query ──────────────────────────
    if artist:
        key_expr = Key("artist").eq(artist)
        if year:
            key_expr = key_expr & Key("year").eq(year)

        supplemental_filters = []
        if title:
            supplemental_filters.append(Attr("title").eq(title))
        if album:
            supplemental_filters.append(Attr("album").eq(album))

        call_kwargs: dict = {
            "IndexName":              settings.PERFORMER_GSI,
            "KeyConditionExpression": key_expr,
        }
        extra = _combine_filters(supplemental_filters)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        result = _catalogue_tbl.query(**call_kwargs)
        return result.get("Items", [])

    # ── Branch B: track name present, no performer → table / LSI query ────────
    if title:
        key_expr = Key("title").eq(title)

        supplemental_filters = []
        if album:
            supplemental_filters.append(Attr("album").eq(album))

        if year:
            key_expr = key_expr & Key("year").eq(year)
            call_kwargs = {
                "IndexName":              settings.TRACK_LSI,
                "KeyConditionExpression": key_expr,
            }
        else:
            call_kwargs = {"KeyConditionExpression": key_expr}

        extra = _combine_filters(supplemental_filters)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        result = _catalogue_tbl.query(**call_kwargs)
        return result.get("Items", [])

    # ── Branch C: only year / album supplied → full scan ──────────────────────
    scan_conditions = []
    if year:
        scan_conditions.append(Attr("year").eq(year))
    if album:
        scan_conditions.append(Attr("album").eq(album))

    call_kwargs = {}
    extra = _combine_filters(scan_conditions)
    if extra is not None:
        call_kwargs["FilterExpression"] = extra

    result = _catalogue_tbl.scan(**call_kwargs)
    return result.get("Items", [])


# ══════════════════════════════════════════════════════════════════════════════
# Library (subscriptions) operations
# ══════════════════════════════════════════════════════════════════════════════

def _build_entry_key(track: str, performer: str, yr: str) -> str:
    """Construct the composite sort key stored in the library table."""
    return f"{track}#{performer}#{yr}"


def retrieve_library(addr: str) -> list[dict]:
    """
    Fetch all library entries for a given account address.
    Single Query on the email partition key — O(n entries), not a scan.
    """
    outcome = _library_tbl.query(
        KeyConditionExpression=Key("email").eq(addr)
    )
    return outcome.get("Items", [])


def save_to_library(
    email:     str,
    title:     str,
    artist:    str,
    year:      str,
    album:     str,
    image_url: str,
) -> None:
    """
    Write a library entry.  Idempotent — re-adding an existing entry is a no-op.
    """
    composite_id = _build_entry_key(title, artist, year)
    _library_tbl.put_item(
        Item={
            "email":     email,
            "song_id":   composite_id,
            "title":     title,
            "artist":    artist,
            "year":      year,
            "album":     album,
            "image_url": image_url,
        }
    )


def drop_from_library(email: str, title: str, artist: str, year: str) -> None:
    """
    Delete a library entry by its exact composite primary key.
    No-op when the entry does not exist.
    """
    composite_id = _build_entry_key(title, artist, year)
    _library_tbl.delete_item(
        Key={
            "email":   email,
            "song_id": composite_id,
        }
    )
