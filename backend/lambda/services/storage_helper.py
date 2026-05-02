"""
services/storage_helper.py

Generates time-limited S3 access tokens for the Lambda backend.

Lambda-specific note
────────────────────
generate_presigned_url() performs a local cryptographic computation —
it does NOT make a network call to S3. The module-level client is
created once per cold start and reused across warm invocations,
saving HTTPS connection establishment overhead on every request.
"""

import boto3
from botocore.exceptions import ClientError

import settings

_signing_client = boto3.client("s3", region_name=settings.CLOUD_REGION)


def generate_access_token(filename: str) -> str | None:
    """
    Sign a GET request for the given S3 object key.

    Parameters
    ----------
    filename : str
        Object key in the image bucket (e.g. "TaylorSwift.jpg").

    Returns
    -------
    str  — signed URL valid for SIGNED_URL_TTL seconds.
    None — if signing fails (object absent, bucket misconfigured, etc.)
    """
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
    """
    Add a 'presigned_url' field to a DynamoDB row by deriving the S3 key
    from the stored 'image_url' attribute (basename of the original URL).
    """
    source_url = record.get("image_url", "")
    basename   = source_url.split("/")[-1] if source_url else ""
    record["presigned_url"] = generate_access_token(basename) if basename else None
    return record
