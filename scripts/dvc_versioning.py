#!/usr/bin/env python3
"""
DVC Versioning Helper Script
Automates DVC versioning workflow for processed data.
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DVCVersioning:
    """Handles DVC versioning operations."""

    def __init__(self, repo_path: str = "."):
        """Initialize DVC versioning."""
        self.repo_path = Path(repo_path)
        os.chdir(self.repo_path)

    def check_dvc_initialized(self) -> bool:
        """Check if DVC is initialized."""
        return (self.repo_path / ".dvc").exists()

    def initialize_dvc(self, remote_url: str, remote_name: str = "gcs-remote"):
        """Initialize DVC repository."""
        if not self.check_dvc_initialized():
            logger.info("Initializing DVC repository...")
            subprocess.run(["dvc", "init"], check=True)
            logger.info("DVC initialized")

        # Add remote if not exists
        try:
            subprocess.run(
                ["dvc", "remote", "add", "-d", remote_name, remote_url],
                check=True,
                capture_output=True
            )
            logger.info(f"Added DVC remote: {remote_name} -> {remote_url}")
        except subprocess.CalledProcessError as e:
            if "already exists" in str(e.stderr):
                logger.info(f"Remote {remote_name} already exists")
            else:
                raise

    def add_data(self, data_path: str, message: Optional[str] = None) -> bool:
        """Add data to DVC tracking."""
        data_path_obj = Path(data_path)
        if not data_path_obj.exists():
            logger.error(f"Data path {data_path} does not exist")
            return False

        try:
            cmd = ["dvc", "add", str(data_path)]
            subprocess.run(cmd, check=True)
            logger.info(f"Added {data_path} to DVC")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add data: {e}")
            return False

    def push_data(self) -> bool:
        """Push data to remote storage."""
        try:
            subprocess.run(["dvc", "push"], check=True)
            logger.info("Pushed data to remote")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push data: {e}")
            return False

    def create_version_tag(
        self,
        version_tag: str,
        metadata: Optional[Dict] = None,
        commit_message: Optional[str] = None
    ) -> bool:
        """Create a version tag with metadata."""
        try:
            # Add .dvc files to git
            subprocess.run(["git", "add", "*.dvc", ".dvc/config"], check=True)

            # Commit
            if not commit_message:
                commit_message = f"Version {version_tag} - {datetime.now().isoformat()}"

            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True,
                capture_output=True
            )
            logger.info(f"Committed version {version_tag}")

            # Create git tag
            tag_message = json.dumps(
                metadata) if metadata else f"Version {version_tag}"
            subprocess.run(
                ["git", "tag", "-a", version_tag, "-m", tag_message],
                check=True
            )
            logger.info(f"Created tag {version_tag}")

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create version tag: {e}")
            return False

    def version_data(
        self,
        data_path: str,
        version_tag: str,
        metadata: Optional[Dict] = None,
        push: bool = True
    ) -> bool:
        """Complete versioning workflow."""
        logger.info(f"Versioning {data_path} as {version_tag}")

        # Add data
        if not self.add_data(data_path):
            return False

        # Push to remote
        if push:
            if not self.push_data():
                return False

        # Create version tag
        if not self.create_version_tag(version_tag, metadata):
            return False

        logger.info(f"Successfully versioned {data_path} as {version_tag}")
        return True


def load_config(config_path: str = "config/pipeline_config.yaml") -> dict:
    """Load configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="DVC Versioning Helper")
    parser.add_argument(
        "--data-path",
        type=str,
        required=True,
        help="Path to data to version"
    )
    parser.add_argument(
        "--version-tag",
        type=str,
        required=True,
        help="Version tag (e.g., v1.0)"
    )
    parser.add_argument(
        "--metadata",
        type=str,
        help="Path to metadata JSON file"
    )
    parser.add_argument(
        "--remote-url",
        type=str,
        help="DVC remote URL (for initialization)"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push to remote"
    )

    args = parser.parse_args()

    # Load metadata if provided
    metadata = None
    if args.metadata and os.path.exists(args.metadata):
        with open(args.metadata, 'r') as f:
            metadata = json.load(f)

    # Initialize DVC versioning
    dvc = DVCVersioning()

    # Initialize DVC if needed
    if args.remote_url:
        dvc.initialize_dvc(args.remote_url)

    # Version data
    success = dvc.version_data(
        args.data_path,
        args.version_tag,
        metadata=metadata,
        push=not args.no_push
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
