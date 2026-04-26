"""
create_music_table.py

Provisions the 'music' DynamoDB table with a purposefully designed key schema,
one Global Secondary Index (GSI), and one Local Secondary Index (LSI).

─── Key Schema Rationale ────────────────────────────────────────────────────────

Dataset analysis (2026a2_songs.json, 137 songs):

  ▸ title alone          → NOT unique. "Bad Blood" exists for Taylor Swift AND
                            Kendrick Lamar. Multiple titles are shared across artists.

  ▸ (title + artist)     → NOT unique. "Delicate" by Taylor Swift appears under
                            two album editions with different years (2017, 2018).
                            Same applies to "We Are Never Ever Getting Back Together"
                            (2012, 2013) and "I Won't Give Up" (2012, 2021).

  ▸ (title + artist + year) → UNIQUE across all 137 songs. This is the minimal
                            composite identity needed to avoid silent overwrites.

  Design:
    Partition key : title           (String)
    Sort key      : artist#year     (String) — e.g. "Taylor Swift#2017"

    The composite sort key packs both differentiating fields into one attribute,
    fully satisfying DynamoDB's two-key schema while ensuring zero data loss.

─── Index Design ────────────────────────────────────────────────────────────────

  GSI  "artist-index"
    PK: artist  (String)
    SK: year    (String)
    → Efficient query for "all songs by artist" or "all songs by artist in year".
      Covers the demo scenario: "find all songs by Taylor Swift in album Fearless"
      and "find all songs of Jimmy Buffett in 1974".

  LSI  "title-year-index"
    PK: title   (String)   [must match table PK for an LSI]
    SK: year    (String)
    → Supports title + year range queries, avoiding a full scan when both
      title and year are provided but artist is unknown.

Both indexes use ALL projection — all item attributes are available without
needing a secondary read against the base table.

Usage:
    python scripts/create_music_table.py
"""

import boto3
from botocore.exceptions import ClientError

# ── AWS settings ───────────────────────────────────────────────────────────────
AWS_REGION  = "us-east-1"
MUSIC_TBL   = "music"

# ── Index name constants ───────────────────────────────────────────────────────
GSI_BY_ARTIST = "artist-index"
LSI_BY_YEAR   = "title-year-index"

# ── Boto3 setup ────────────────────────────────────────────────────────────────
db_resource = boto3.resource("dynamodb", region_name=AWS_REGION)


# ── Table provisioning ─────────────────────────────────────────────────────────

def provision_music_table():
    """
    Create the music table with GSI and LSI.
    Skips gracefully if the table already exists.
    """
    key_definitions = [
        # Primary key attributes
        {"AttributeName": "title",       "AttributeType": "S"},
        {"AttributeName": "artist#year", "AttributeType": "S"},
        # GSI partition key
        {"AttributeName": "artist",      "AttributeType": "S"},
        # Shared sort key for GSI + LSI
        {"AttributeName": "year",        "AttributeType": "S"},
    ]

    primary_key_schema = [
        {"AttributeName": "title",       "KeyType": "HASH"},
        {"AttributeName": "artist#year", "KeyType": "RANGE"},
    ]

    gsi_definitions = [
        {
            "IndexName": GSI_BY_ARTIST,
            "KeySchema": [
                {"AttributeName": "artist", "KeyType": "HASH"},
                {"AttributeName": "year",   "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }
    ]

    lsi_definitions = [
        {
            "IndexName": LSI_BY_YEAR,
            "KeySchema": [
                {"AttributeName": "title", "KeyType": "HASH"},
                {"AttributeName": "year",  "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }
    ]

    try:
        tbl = db_resource.create_table(
            TableName=MUSIC_TBL,
            KeySchema=primary_key_schema,
            AttributeDefinitions=key_definitions,
            LocalSecondaryIndexes=lsi_definitions,
            GlobalSecondaryIndexes=gsi_definitions,
            BillingMode="PAY_PER_REQUEST",
        )

        print(f"[INFO] Waiting for '{MUSIC_TBL}' to become active...")
        tbl.wait_until_exists()

        print(f"[OK]   '{MUSIC_TBL}' is active and ready.")
        print(f"       Primary key  →  title (PK)  +  artist#year (SK)")
        print(f"       GSI          →  {GSI_BY_ARTIST}  :  artist (PK) + year (SK)")
        print(f"       LSI          →  {LSI_BY_YEAR}  :  title (PK) + year (SK)")
        return tbl

    except ClientError as exc:
        err_code = exc.response["Error"]["Code"]
        if err_code == "ResourceInUseException":
            print(f"[SKIP] '{MUSIC_TBL}' already exists — skipping table creation.")
            return db_resource.Table(MUSIC_TBL)
        raise


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    provision_music_table()
    print("\n[DONE] Music table setup finished.")


if __name__ == "__main__":
    run()
