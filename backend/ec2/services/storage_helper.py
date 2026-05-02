"""
services/storage_helper.py

Generates time-limited access tokens (pre-signed URLs) for artist artwork
stored in a private S3 bucket.

Why not a public bucket?
────────────────────────
Exposing the bucket publicly means any caller with the object URL can access
images permanently and without restriction.  Instead, the backend signs a
short-lived URL at response time; the browser fetches the image directly from
S3 using that URL, which expires after SIGNED_URL_TTL seconds (default 1 h).
The backend never proxies the image bytes, so there is no extra bandwidth cost.
"""

import boto3
from botocore.exceptions import ClientError

import settings

# ── S3 signing client (created once per worker) ────────────────────────────────
_signing_client = boto3.client("s3", region_name=settings.CLOUD_REGION)


def generate_access_token(filename: str) -> str | None:
    """
    Produce a pre-signed GET URL for an object stored in the image bucket.

    Parameters
    ----------
    filename : str
        The S3 object key — identical to the basename of the original img_url,
        e.g. "TaylorSwift.jpg".

    Returns
    -------
    str
        A URL valid for SIGNED_URL_TTL seconds.
    None
        If the object is absent or signing fails.
    """
    try:
        signed_url = _signing_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.IMAGE_BUCKET,
                "Key":    filename,
            },
            ExpiresIn=settings.SIGNED_URL_TTL,
        )
        return signed_url
    except ClientError as exc:
        print(f"[WARN] Token generation failed for '{filename}': {exc}")
        return None


def attach_image_token(record: dict) -> dict:
    """
    Enrich a DynamoDB row with a 'presigned_url' field derived from its
    'image_url' attribute.

    The stored image_url is the original source URL, e.g.:
        https://raw.githubusercontent.com/YingZhang2015/cc/main/TaylorSwift.jpg

    The S3 object key is just the trailing filename: TaylorSwift.jpg

    Mutates and returns the same dict — safe because each record is a fresh
    dict from a DynamoDB response.
    """
    source_url = record.get("image_url", "")
    basename   = source_url.split("/")[-1] if source_url else ""
    record["presigned_url"] = generate_access_token(basename) if basename else None
    return record
