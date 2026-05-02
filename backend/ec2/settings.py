"""
settings.py

Runtime configuration for the EC2 service layer.
All deployment-specific values are pulled from environment variables so the
same codebase runs identically on a developer's laptop, inside Docker, and
on the EC2 instance — the only difference is which env vars are set.
"""

import os

# ── Cloud region ───────────────────────────────────────────────────────────────
CLOUD_REGION = os.environ.get("AWS_REGION", "us-east-1")

# ── Storage table identifiers ──────────────────────────────────────────────────
USERS_TABLE         = "login"
CATALOGUE_TABLE     = "music"
LIBRARY_TABLE       = "subscriptions"

# ── Index handle names ─────────────────────────────────────────────────────────
PERFORMER_GSI  = "artist-index"       # GSI: performer (PK) + release_year (SK)
TRACK_LSI      = "title-year-index"   # LSI: track_name (PK) + release_year (SK)

# ── Media storage ──────────────────────────────────────────────────────────────
# Must match the bucket created by scripts/upload_images_to_s3.py.
# Override via the IMAGE_BUCKET env var to avoid editing this file.
IMAGE_BUCKET      = os.environ.get("S3_BUCKET", "testbuck2003-ashup-2026")
SIGNED_URL_TTL    = int(os.environ.get("PRESIGNED_URL_EXPIRY", 3600))   # seconds

# ── Application ────────────────────────────────────────────────────────────────
APP_SECRET = os.environ.get("SECRET_KEY", "change-me-in-production")
DEV_MODE   = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
