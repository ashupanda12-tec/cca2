"""
services/s3.py

S3 pre-signed URL generation for artist images.

Why pre-signed URLs?
────────────────────
The S3 bucket is private (no public ACL).  Serving images directly via a
public bucket URL would expose the bucket to unauthenticated access, which is
a security anti-pattern.  Instead, the backend generates a short-lived
pre-signed URL for each image on demand; the frontend uses that URL to fetch
the image directly from S3 without the backend becoming a media proxy.

The URL embeds temporary AWS credentials and expires after PRESIGNED_URL_EXPIRY
seconds (default: 3600 s / 1 h).  This satisfies the assessment spec note:
"Students would also need to securely access the objects stored in S3."
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
        The S3 object key, which matches the filename stored during upload
        (e.g. "TaylorSwift.jpg").

    Returns
    -------
    str
        A pre-signed URL valid for PRESIGNED_URL_EXPIRY seconds.
    None
        If the object does not exist or an error occurs.
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
        # Log and return None so callers can degrade gracefully
        print(f"[WARN] Could not generate presigned URL for '{image_filename}': {e}")
        return None


def enrich_with_presigned_url(item: dict) -> dict:
    """
    Given a DynamoDB item dict that contains an 'image_url' field (the raw
    source URL stored during data import), derive the S3 filename and attach
    a 'presigned_url' field.

    The raw image_url is something like:
        https://rmit.instructure.com/.../TaylorSwift.jpg
    The S3 key is just the basename: TaylorSwift.jpg

    Returns the same dict with a new 'presigned_url' key added.
    """
    raw_url = item.get("image_url", "")
    filename = raw_url.split("/")[-1] if raw_url else ""
    item["presigned_url"] = get_presigned_url(filename) if filename else None
    return item
