"""
upload_images_to_s3.py

Reads all artist image URLs from 2026a2_songs.json, downloads each unique
image to a local cache, then uploads them to a private S3 bucket.

Deduplication

  137 songs reference only 71 unique artist images. The URL-to-filename map
  deduplicates automatically — each artist's image is downloaded and uploaded
  exactly once, regardless of how many songs reference it.

Usage:
    python scripts/upload_images_to_s3.py
    python scripts/upload_images_to_s3.py --dry-run    # preview without I/O
"""

import json
import argparse
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── Configuration ──────────────────────────────────────────────────────────────
# Update BUCKET_NAME to your own globally-unique S3 bucket name before running.
# This value must also be set in backend/*/config.py (S3_BUCKET constant).
AWS_REGION   = "us-east-1"
BUCKET_NAME  = "myassignment2bucket-ashup"

REPO_ROOT    = Path(__file__).resolve().parent.parent
SOURCE_JSON  = REPO_ROOT / "data" / "2026a2_songs.json"
LOCAL_CACHE  = REPO_ROOT / "data" / "images"

# ── Boto3 setup ────────────────────────────────────────────────────────────────
s3_client = boto3.client("s3", region_name=AWS_REGION)



# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(preview_mode: bool = False) -> None:
    """
    Full pipeline: read URLs → optionally download → optionally upload.
    When preview_mode is True, only prints the planned operations.
    """
    print(f"[INFO] Reading image URLs from: {SOURCE_JSON}")
    url_index = collect_image_urls(SOURCE_JSON)
    print(f"[INFO] {len(url_index)} unique artist images found.")

    if preview_mode:
        print("[DRY RUN] Planned uploads (no downloads or uploads performed):")
        for img_file, img_url in sorted(url_index.items()):
            print(f"  s3://{BUCKET_NAME}/{img_file}  ←  {img_url}")
        return

    LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
    ensure_bucket(BUCKET_NAME, AWS_REGION)

    uploaded_count = 0
    failed_count   = 0

    for img_file, img_url in sorted(url_index.items()):
        cache_path = LOCAL_CACHE / img_file
        print(f"  → {img_file} ...", end=" ", flush=True)

        downloaded = fetch_image(img_url, cache_path)
        if not downloaded:
            failed_count += 1
            continue

        success = push_to_s3(cache_path, img_file, BUCKET_NAME)
        if success:
            print("done")
            uploaded_count += 1
        else:
            failed_count += 1

    print(f"\n[DONE] {uploaded_count} images uploaded, {failed_count} failed.")
    if uploaded_count > 0:
        print(f"       Bucket: s3://{BUCKET_NAME}/")


# ── URL map builder ────────────────────────────────────────────────────────────

def collect_image_urls(filepath: Path) -> dict:
    """
    Parse the JSON dataset and return a deduplicated mapping of
    filename → source_url for every unique artist image.

    e.g. { "TaylorSwift.jpg": "https://raw.githubusercontent.com/..." }
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        dataset = json.load(fh)

    url_index = {}
    for entry in dataset["songs"]:
        source_url  = entry["img_url"]
        img_filename = source_url.split("/")[-1]      # "TaylorSwift.jpg"
        url_index[img_filename] = source_url           # duplicate keys just overwrite

    return url_index

# ── Image downloader ───────────────────────────────────────────────────────────

def fetch_image(source_url: str, dest_path: Path) -> bool:
    """
    Download the image at source_url to dest_path.
    Returns True on success. Skips the download if the file is already cached.
    """
    if dest_path.exists():
        return True
    try:
        urllib.request.urlretrieve(source_url, dest_path)
        return True
    except Exception as exc:
        print(f"  [WARN] Download failed for {source_url}: {exc}")
        return False


# ── S3 uploader ────────────────────────────────────────────────────────────────

def push_to_s3(local_path: Path, object_key: str, bucket_name: str) -> bool:
    """
    Upload a local file to S3 under object_key.
    Returns True on success.
    """
    try:
        s3_client.upload_file(
            str(local_path),
            bucket_name,
            object_key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
        return True
    except ClientError as exc:
        print(f"  [ERROR] Upload failed for '{object_key}': {exc}")
        return False





# ── Bucket management ──────────────────────────────────────────────────────────

def ensure_bucket(bucket_name: str, region: str) -> None:
    """
    Create the S3 bucket if it does not exist.
    Handles the us-east-1 quirk where LocationConstraint must be omitted.
    """
    try:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"[OK]   Created bucket '{bucket_name}'.")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"[INFO] Bucket '{bucket_name}' already exists — continuing.")
        else:
            raise
# ── Entry point ────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="Upload artist images to S3.")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned uploads without performing any I/O.",
    )
    return ap.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    run_pipeline(preview_mode=cli_args.dry_run)
