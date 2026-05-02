"""
settings.py

Runtime configuration for the ECS Fargate service.

Identical constants to the EC2 variant — both backends share the same
DynamoDB tables and S3 bucket. Only the compute layer differs.

When running in ECS, the LabRole task role supplies AWS credentials
automatically. Locally, boto3 reads from ~/.aws/credentials (mounted
read-only via docker-compose.yml).
"""

import os

# ── Cloud region ───────────────────────────────────────────────────────────────
CLOUD_REGION = os.environ.get("AWS_REGION", "us-east-1")

# ── DynamoDB table names ───────────────────────────────────────────────────────
USERS_TABLE      = "login"
CATALOGUE_TABLE  = "music"
LIBRARY_TABLE    = "subscriptions"

# ── Index names ────────────────────────────────────────────────────────────────
PERFORMER_GSI = "artist-index"       # GSI: artist (PK) + year (SK)
TRACK_LSI     = "title-year-index"   # LSI: title  (PK) + year (SK)

# ── Image storage ──────────────────────────────────────────────────────────────
IMAGE_BUCKET   = os.environ.get("S3_BUCKET", "teststage2026")
SIGNED_URL_TTL = int(os.environ.get("PRESIGNED_URL_EXPIRY", 3600))

# ── Flask ──────────────────────────────────────────────────────────────────────
APP_SECRET = os.environ.get("SECRET_KEY", "change-me-in-production")
DEV_MODE   = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
