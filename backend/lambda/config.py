"""
config.py

Central configuration for the Lambda backend.
Identical constants to the EC2 backend so both implementations are
interchangeable — only the compute layer differs.

In Lambda, AWS_REGION is injected automatically by the runtime.
All other values are hard-coded here (or can be moved to Lambda
environment variables via the SAM template for easy overrides).
"""

import os

# ── AWS ────────────────────────────────────────────────────────────────────────
# Lambda runtime sets AWS_REGION automatically; fall back to us-east-1 locally.
REGION = os.environ.get("AWS_REGION", "us-east-1")

# ── DynamoDB table names ───────────────────────────────────────────────────────
LOGIN_TABLE         = "login"
MUSIC_TABLE         = "music"
SUBSCRIPTIONS_TABLE = "subscriptions"

# ── DynamoDB index names ───────────────────────────────────────────────────────
ARTIST_GSI = "artist-index"       # artist (PK) + year (SK)
TITLE_LSI  = "title-year-index"   # title  (PK) + year (SK)

# ── S3 ─────────────────────────────────────────────────────────────────────────
# Set the S3_BUCKET environment variable to your own bucket name, or update
# the default value below.  The bucket must exist and contain the artist images
# uploaded by scripts/upload_images_to_s3.py.
S3_BUCKET            = os.environ.get("S3_BUCKET", "testbuck2003-ashup-2026")
PRESIGNED_URL_EXPIRY = int(os.environ.get("PRESIGNED_URL_EXPIRY", 3600))  # seconds
