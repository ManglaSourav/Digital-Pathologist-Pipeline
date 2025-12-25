#!/usr/bin/env python3
"""
GCS Upload Utility Script
Uploads local image data to Google Cloud Storage with progress tracking.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GCSUploader:
    """Handles uploading files to GCS with progress tracking."""

    def __init__(self, bucket_name: str, credentials_path: Optional[str] = None):
        """
        Initialize GCS uploader.

        Args:
            bucket_name: Name of the GCS bucket
            credentials_path: Path to service account JSON key (optional)
        """
        self.bucket_name = bucket_name
        if credentials_path and os.path.exists(credentials_path):
            self.client = storage.Client.from_service_account_json(
                credentials_path)
        else:
            self.client = storage.Client()

        try:
            self.bucket = self.client.bucket(bucket_name)
            # Check if bucket exists, create if not
            if not self.bucket.exists():
                logger.warning(
                    f"Bucket {bucket_name} does not exist. Creating...")
                self.bucket.create()
                logger.info(f"Bucket {bucket_name} created successfully")
        except GoogleCloudError as e:
            logger.error(f"Error accessing bucket: {e}")
            raise

    def upload_file(self, local_path: str, gcs_path: str) -> bool:
        """
        Upload a single file to GCS.

        Args:
            local_path: Local file path
            gcs_path: Destination path in GCS

        Returns:
            True if successful, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)
            return True
        except Exception as e:
            logger.error(f"Error uploading {local_path}: {e}")
            return False

    def upload_directory(
        self,
        local_dir: str,
        gcs_prefix: str,
        file_extensions: Optional[list] = None,
        preserve_structure: bool = True
    ) -> dict:
        """
        Upload directory to GCS with progress tracking.

        Args:
            local_dir: Local directory path
            gcs_prefix: GCS path prefix (e.g., 'raw/v1.0/')
            file_extensions: List of file extensions to include (e.g., ['.jpeg', '.jpg'])
            preserve_structure: Whether to preserve directory structure

        Returns:
            Dictionary with upload statistics
        """
        local_path = Path(local_dir)
        if not local_path.exists():
            logger.error(f"Local directory {local_dir} does not exist")
            return {"success": False, "uploaded": 0, "failed": 0}

        # Find all files
        files_to_upload = []
        if file_extensions:
            for ext in file_extensions:
                files_to_upload.extend(local_path.rglob(f"*{ext}"))
        else:
            files_to_upload = list(local_path.rglob("*"))
            files_to_upload = [f for f in files_to_upload if f.is_file()]

        logger.info(f"Found {len(files_to_upload)} files to upload")

        uploaded = 0
        failed = 0

        # Upload with progress bar
        with tqdm(total=len(files_to_upload), desc="Uploading", unit="file") as pbar:
            for local_file in files_to_upload:
                if preserve_structure:
                    # Preserve relative path structure
                    relative_path = local_file.relative_to(local_path)
                    gcs_path = f"{gcs_prefix.rstrip('/')}/{str(relative_path).replace(os.sep, '/')}"
                else:
                    # Just use filename
                    gcs_path = f"{gcs_prefix.rstrip('/')}/{local_file.name}"

                if self.upload_file(str(local_file), gcs_path):
                    uploaded += 1
                else:
                    failed += 1

                pbar.update(1)
                pbar.set_postfix({"uploaded": uploaded, "failed": failed})

        logger.info(f"Upload complete: {uploaded} successful, {failed} failed")
        return {
            "success": failed == 0,
            "uploaded": uploaded,
            "failed": failed,
            "total": len(files_to_upload)
        }


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main entry point for upload script."""
    import argparse

    parser = argparse.ArgumentParser(description="Upload images to GCS")
    parser.add_argument(
        "--local-dir",
        type=str,
        required=True,
        help="Local directory containing images"
    )
    parser.add_argument(
        "--gcs-bucket",
        type=str,
        required=True,
        help="GCS bucket name"
    )
    parser.add_argument(
        "--gcs-prefix",
        type=str,
        default="raw/v1.0",
        help="GCS path prefix (default: raw/v1.0)"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to gcp_config.yaml (optional)"
    )
    parser.add_argument(
        "--credentials",
        type=str,
        help="Path to service account JSON key (optional)"
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".jpeg", ".jpg", ".png"],
        help="File extensions to upload (default: .jpeg .jpg .png)"
    )

    args = parser.parse_args()

    # Load config if provided
    credentials_path = args.credentials
    if args.config:
        config = load_config(args.config)
        if not credentials_path and "service_account" in config.get("gcp", {}):
            credentials_path = config["gcp"]["service_account"].get("key_path")

    # Initialize uploader
    try:
        uploader = GCSUploader(args.gcs_bucket, credentials_path)
    except Exception as e:
        logger.error(f"Failed to initialize GCS uploader: {e}")
        sys.exit(1)

    # Upload directory
    result = uploader.upload_directory(
        args.local_dir,
        args.gcs_prefix,
        file_extensions=args.extensions
    )

    if result["success"]:
        logger.info("All files uploaded successfully!")
        sys.exit(0)
    else:
        logger.warning(f"Upload completed with {result['failed']} failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
