"""
config.py

Central configuration for the EC2 Flask backend.
All environment-specific values are read from environment variables so the
same codebase works in development (with ~/.aws credentials) and on EC2
(with the LabRole instance profile).
"""

import os

# ── AWS ────────────────────────────────────────────────────────────────────────
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

# ── Flask ──────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
DEBUG      = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
