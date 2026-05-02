"""
services/db_gateway.py

All DynamoDB operations for the ECS backend.
Identical logic to the EC2 variant — shared table schema, identical index
routing, identical write patterns.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import settings

_db = boto3.resource("dynamodb", region_name=settings.CLOUD_REGION)

_users_tbl     = _db.Table(settings.USERS_TABLE)
_catalogue_tbl = _db.Table(settings.CATALOGUE_TABLE)
_library_tbl   = _db.Table(settings.LIBRARY_TABLE)


# ── Account helpers ────────────────────────────────────────────────────────────

def fetch_account(addr: str) -> dict | None:
    outcome = _users_tbl.get_item(Key={"email": addr})
    return outcome.get("Item")


def insert_account(addr: str, display_name: str, secret: str) -> None:
    _users_tbl.put_item(
        Item={
            "email":     addr,
            "user_name": display_name,
            "password":  secret,
        },
        ConditionExpression="attribute_not_exists(email)",
    )


# ── Catalogue helpers ──────────────────────────────────────────────────────────

def _combine_filters(conditions: list):
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
    # Branch A — performer present → GSI
    if artist:
        key_expr = Key("artist").eq(artist)
        if year:
            key_expr = key_expr & Key("year").eq(year)

        filters = []
        if title:
            filters.append(Attr("title").eq(title))
        if album:
            filters.append(Attr("album").eq(album))

        call_kwargs: dict = {
            "IndexName":              settings.PERFORMER_GSI,
            "KeyConditionExpression": key_expr,
        }
        extra = _combine_filters(filters)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        return _catalogue_tbl.query(**call_kwargs).get("Items", [])

    # Branch B — track name present → main table or LSI
    if title:
        key_expr = Key("title").eq(title)

        filters = []
        if album:
            filters.append(Attr("album").eq(album))

        if year:
            key_expr = key_expr & Key("year").eq(year)
            call_kwargs = {
                "IndexName":              settings.TRACK_LSI,
                "KeyConditionExpression": key_expr,
            }
        else:
            call_kwargs = {"KeyConditionExpression": key_expr}

        extra = _combine_filters(filters)
        if extra is not None:
            call_kwargs["FilterExpression"] = extra

        return _catalogue_tbl.query(**call_kwargs).get("Items", [])

    # Branch C — year / album only → full scan
    scan_conditions = []
    if year:
        scan_conditions.append(Attr("year").eq(year))
    if album:
        scan_conditions.append(Attr("album").eq(album))

    call_kwargs = {}
    extra = _combine_filters(scan_conditions)
    if extra is not None:
        call_kwargs["FilterExpression"] = extra

    return _catalogue_tbl.scan(**call_kwargs).get("Items", [])


# ── Library helpers ────────────────────────────────────────────────────────────

def _build_entry_key(track: str, performer: str, yr: str) -> str:
    return f"{track}#{performer}#{yr}"


def retrieve_library(addr: str) -> list[dict]:
    outcome = _library_tbl.query(
        KeyConditionExpression=Key("email").eq(addr)
    )
    return outcome.get("Items", [])


def save_to_library(
    email: str, title: str, artist: str,
    year: str, album: str, image_url: str,
) -> None:
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
    composite_id = _build_entry_key(title, artist, year)
    _library_tbl.delete_item(
        Key={"email": email, "song_id": composite_id}
    )
