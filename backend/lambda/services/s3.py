"""
services/s3.py

S3 pre-signed URL generation for artist images.

Identical to the EC2 backend's services/s3.py.

Why pre-signed URLs?
────────────────────
The S3 bucket is private.  The Lambda function generates a short-lived
pre-signed URL for each artist image so the frontend can fetch images
directly from S3 without the Lambda becoming a media proxy (which would
waste both Lambda execution time and data-transfer costs).
"""

import boto3
from botocore.exceptions import ClientError

import config

# ── S3 client ──────────────────────────────────────────────────────────────────
_s3_client = boto3.client("s3", region_name=config.REGION)


def get_presigned_url(image_filename: str) -> str | None:
    """
    Generate a pre-signed GET URL for the given S3 object key.

    Parameters
    ----------
    image_filename : str
        The S3 object key, e.g. "TaylorSwift.jpg".

    Returns
    -------
    str  — pre-signed URL valid for PRESIGNED_URL_EXPIRY seconds.
    None — if the object does not exist or an error occurs.
    """
    try:
        url = _s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": config.S3_BUCKET,
                "Key":    image_filename,
            },
            ExpiresIn=config.PRESIGNED_URL_EXPIRY,
        )
        return url
    except ClientError as e:
        print(f"[WARN] Could not generate presigned URL for '{image_filename}': {e}")
        return None


def enrich_with_presigned_url(item: dict) -> dict:
    """
    Given a DynamoDB item dict with an 'image_url' field (the raw source URL
    stored during data import), derive the S3 filename and attach a
    'presigned_url' field.

    The raw image_url is something like:
        https://rmit.instructure.com/.../TaylorSwift.jpg
    The S3 key is just the basename: TaylorSwift.jpg
    """
    raw_url  = item.get("image_url", "")
    filename = raw_url.split("/")[-1] if raw_url else ""
    item["presigned_url"] = get_presigned_url(filename) if filename else None
    return item
