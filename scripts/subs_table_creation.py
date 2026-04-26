"""
create_subscriptions_table.py

Provisions the 'subscriptions' DynamoDB table used to track each user's
saved songs.

─── Schema Design ───────────────────────────────────────────────────────────────

  Partition key : email    (String) — identifies the account holder
  Sort key      : song_id  (String) — composite "title#artist#year"

  Choosing a composite sort key gives us three things at once:

    1. One Query call retrieves all subscriptions for a user (keyed on email).
    2. One DeleteItem call removes a specific subscription by exact key —
       no scan or filter expression required.
    3. The format is naturally collision-free: two songs with the same title
       but different artist or year produce different song_id values.

  Example item:
    email   = "s1234567@student.rmit.edu.au"
    song_id = "Love Story#Taylor Swift#2008"
    title   = "Love Story"
    artist  = "Taylor Swift"
    year    = "2008"
    album   = "Fearless"
    image_url = "https://..."

Usage:
    python scripts/create_subscriptions_table.py
"""

import boto3
from botocore.exceptions import ClientError

# ── AWS settings ───────────────────────────────────────────────────────────────
AWS_REGION   = "us-east-1"
SUBS_TBL     = "subscriptions"

# ── Boto3 setup ────────────────────────────────────────────────────────────────
db_resource = boto3.resource("dynamodb", region_name=AWS_REGION)


# ── Table provisioning ─────────────────────────────────────────────────────────

def provision_subscriptions_table():
    """
    Create the subscriptions table using on-demand billing.
    Skips gracefully when the table already exists.
    """
    pk_schema = [
        {"AttributeName": "email",   "KeyType": "HASH"},
        {"AttributeName": "song_id", "KeyType": "RANGE"},
    ]

    attr_defs = [
        {"AttributeName": "email",   "AttributeType": "S"},
        {"AttributeName": "song_id", "AttributeType": "S"},
    ]

    try:
        tbl = db_resource.create_table(
            TableName=SUBS_TBL,
            KeySchema=pk_schema,
            AttributeDefinitions=attr_defs,
            BillingMode="PAY_PER_REQUEST",
        )

        print(f"[INFO] Waiting for '{SUBS_TBL}' to become active...")
        tbl.wait_until_exists()

        print(f"[OK]   '{SUBS_TBL}' is active and ready.")
        print(f"       Partition key  →  email   (String)")
        print(f"       Sort key       →  song_id (String)  format: title#artist#year")

    except ClientError as exc:
        err_code = exc.response["Error"]["Code"]
        if err_code == "ResourceInUseException":
            print(f"[SKIP] '{SUBS_TBL}' already exists — skipping table creation.")
        else:
            raise


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    provision_subscriptions_table()
    print("\n[DONE] Subscriptions table setup finished.")


if __name__ == "__main__":
    run()
