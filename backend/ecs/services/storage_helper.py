"""
services/storage_helper.py

Generates time-limited S3 access tokens for the ECS backend.
Identical to the EC2 variant — same bucket, same TTL, same derivation logic.
"""

import boto3
from botocore.exceptions import ClientError

import settings

_signing_client = boto3.client("s3", region_name=settings.CLOUD_REGION)


def generate_access_token(filename: str) -> str | None:
    try:
        return _signing_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.IMAGE_BUCKET, "Key": filename},
            ExpiresIn=settings.SIGNED_URL_TTL,
        )
    except ClientError as exc:
        print(f"[WARN] Token generation failed for '{filename}': {exc}")
        return None


def attach_image_token(record: dict) -> dict:
    source_url = record.get("image_url", "")
    basename   = source_url.split("/")[-1] if source_url else ""
    record["presigned_url"] = generate_access_token(basename) if basename else None
    return record
