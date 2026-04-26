"""
create_login_table.py

Provisions the 'login' DynamoDB table and seeds it with 10 user records.

Table design:
  Primary key  → email (String, partition key only)
  Attributes   → user_name (String), password (String)

Note: Plain-text passwords are used here as permitted by the assessment spec
for simplicity. In any real production system, passwords must be salted and
hashed before storage.

Usage:
    python scripts/create_login_table.py
"""

import boto3
from botocore.exceptions import ClientError

# ── Student-specific constants (update before running) ─────────────────────────
# Replace these placeholders with your own details.
# Generates emails: <SID>0@student.rmit.edu.au … <SID>9@student.rmit.edu.au
SID         = "s4109620"
FIRST_NAME  = "Ashutosh"
LAST_NAME = "Panda"

# ── AWS settings ───────────────────────────────────────────────────────────────
AWS_REGION   = "us-east-1"
LOGIN_TBL    = "login"

# ── Seed password list (index matches user suffix 0-9) ─────────────────────────
SEED_PASSWORDS = [
    "012345",
    "123456",
    "234567",
    "345678",
    "456789",
    "567890",
    "678901",
    "789012",
    "890123",
    "901234",
]

# ── Boto3 setup ────────────────────────────────────────────────────────────────
db_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
db_client   = boto3.client("dynamodb",   region_name=AWS_REGION)


# ── Table provisioning ─────────────────────────────────────────────────────────

def provision_login_table():
    """
    Create the login table using on-demand billing.
    Returns the Table object whether newly created or pre-existing.
    """
    try:
        tbl = db_resource.create_table(
            TableName=LOGIN_TBL,
            KeySchema=[
                {"AttributeName": "email", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"[INFO] Waiting for '{LOGIN_TBL}' to become active...")
        tbl.wait_until_exists()
        print(f"[OK]   '{LOGIN_TBL}' is active and ready.")
        return tbl

    except ClientError as exc:
        err_code = exc.response["Error"]["Code"]
        if err_code == "ResourceInUseException":
            print(f"[SKIP] '{LOGIN_TBL}' already exists — skipping table creation.")
            return db_resource.Table(LOGIN_TBL)
        raise


# ── Seed data builder ──────────────────────────────────────────────────────────

def build_seed_records():
    """
    Produce a list of 10 user dicts derived from the student constants above.
    Each record maps cleanly to a DynamoDB item.
    """
    records = []
    for idx in range(10):
        records.append({
            "email":     f"{SID}{idx}@student.rmit.edu.au",
            "user_name": f"{FIRST_NAME}{LAST_NAME}{idx}",
            "password":  SEED_PASSWORDS[idx],
        })
    return records


# ── Batch writer ───────────────────────────────────────────────────────────────

def seed_users(tbl, records):
    """Write all seed records to the login table via batch_writer."""
    print(f"[INFO] Seeding {len(records)} user records into '{LOGIN_TBL}'...")
    with tbl.batch_writer() as writer:
        for rec in records:
            writer.put_item(Item=rec)
            print(f"  → {rec['email']}  |  {rec['user_name']}  |  {rec['password']}")
    print(f"[OK]   Seed complete — {len(records)} records written.")


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    login_tbl = provision_login_table()
    user_records = build_seed_records()
    seed_users(login_tbl, user_records)
    print("\n[DONE] Login table setup finished.")


if __name__ == "__main__":
    run()
