"""
settings.py

Runtime constants for the Lambda backend.
Identical values to the EC2/ECS variants — all three compute options share
the same DynamoDB tables and S3 bucket.

Lambda automatically injects AWS_REGION into the execution environment.
All other settings can be overridden via Lambda environment variables defined
in the SAM template's Globals.Function.Environment section.
"""

import os

CLOUD_REGION    = os.environ.get("AWS_REGION", "us-east-1")

USERS_TABLE     = "login"
CATALOGUE_TABLE = "music"
LIBRARY_TABLE   = "subscriptions"

PERFORMER_GSI   = "artist-index"
TRACK_LSI       = "title-year-index"

IMAGE_BUCKET    = os.environ.get("S3_BUCKET", "testbuck2003-ashup-2026")
SIGNED_URL_TTL  = int(os.environ.get("PRESIGNED_URL_EXPIRY", 3600))
