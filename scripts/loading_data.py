"""
load_music_data.py

Reads all song entries from 2026a2_songs.json and writes them into the
'music' DynamoDB table without loss or collision.

─── Data Integrity Guarantee ────────────────────────────────────────────────────

  Before writing, every (title, artist, year) triple is checked for
  uniqueness. The table's sort key — stored as "artist#year" — encodes both
  the artist and year in a single DynamoDB attribute, making the primary key
  (title, artist#year) unique for all 137 songs in the dataset.

  The JSON source field is "img_url"; it is stored in DynamoDB as "image_url"
  to match the attribute name required by the application spec.

  boto3's batch_writer automatically handles retries for any unprocessed
  items returned by DynamoDB, so the load is reliable even under throttling.

Usage:
    python scripts/load_music_data.py
    python scripts/load_music_data.py --dry-run    # preview without writing
"""

import json
import argparse
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── File paths ─────────────────────────────────────────────────────────────────
REPO_ROOT  = Path(__file__).resolve().parent.parent
SOURCE_JSON = REPO_ROOT / "data" / "2026a2_songs.json"

# ── AWS settings ───────────────────────────────────────────────────────────────
AWS_REGION = "us-east-1"
MUSIC_TBL  = "music"

# ── Boto3 setup ────────────────────────────────────────────────────────────────
db_resource = boto3.resource("dynamodb", region_name=AWS_REGION)




# ── Uniqueness validator ───────────────────────────────────────────────────────

def assert_no_duplicate_keys(song_list: list) -> None:
    """
    Verify that every (title, artist, year) triple is unique.
    Raises ValueError immediately if a duplicate is detected — this would
    cause a silent overwrite in DynamoDB and violate the lossless import
    requirement from the assessment spec.
    """
    observed = set()
    for entry in song_list:
        identity = (entry["title"], entry["artist"], entry["year"])
        if identity in observed:
            raise ValueError(
                f"Duplicate song key detected — would overwrite in DynamoDB: {identity}"
            )
        observed.add(identity)

    print(f"[OK]   Uniqueness check passed: all {len(song_list)} songs "
          f"have distinct (title, artist, year) keys.")


# ── Item builder ───────────────────────────────────────────────────────────────

def to_dynamo_item(raw: dict) -> dict:
    """
    Convert a raw JSON song record into a DynamoDB-ready item.

    Mapping:
      raw["img_url"]  →  item["image_url"]   (spec-required attribute name)
      (artist, year)  →  item["artist#year"]  (composite sort key)
      artist and year are also stored as separate top-level attributes
      so they are queryable via the GSI and LSI, and filterable in app queries.
    """
    composite_sk = f"{raw['artist']}#{raw['year']}"
    return {
        "title":       raw["title"],
        "artist#year": composite_sk,
        "artist":      raw["artist"],
        "year":        raw["year"],
        "album":       raw["album"],
        "image_url":   raw["img_url"],
    }

# ── JSON reader ────────────────────────────────────────────────────────────────

def fetch_song_list(filepath: Path) -> list:
    """Parse the JSON file and return the raw list of song dicts."""
    with open(filepath, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["songs"]

# ── Batch writer ───────────────────────────────────────────────────────────────

def write_songs(song_list: list, preview_mode: bool = False) -> None:
    """
    Insert all songs into the music table via batch_writer.
    When preview_mode is True, prints the planned writes without touching DynamoDB.
    """
    if preview_mode:
        print(f"[DRY RUN] {len(song_list)} songs would be written — no changes made.")
        for idx, raw in enumerate(song_list, start=1):
            item = to_dynamo_item(raw)
            print(f"  [{idx:03}]  PK={item['title']!r}  SK={item['artist#year']!r}")
        return

    tbl = db_resource.Table(MUSIC_TBL)
    print(f"[INFO] Writing {len(song_list)} songs to '{MUSIC_TBL}'...")

    with tbl.batch_writer() as writer:
        for raw in song_list:
            writer.put_item(Item=to_dynamo_item(raw))

    print(f"[OK]   {len(song_list)} songs written successfully.")


# ── Entry point ────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Load 2026a2_songs.json into DynamoDB.")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned writes without modifying DynamoDB.",
    )
    return ap.parse_args()


def main():
    args = parse_args()

    print(f"[INFO] Reading source file: {SOURCE_JSON}")
    songs = fetch_song_list(SOURCE_JSON)
    print(f"[INFO] {len(songs)} songs found in dataset.")

    assert_no_duplicate_keys(songs)
    write_songs(songs, preview_mode=args.dry_run)

    if not args.dry_run:
        print("\n[DONE] Music data load complete.")


if __name__ == "__main__":
    main()
