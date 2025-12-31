#!/usr/bin/env python3
"""
Local Image Processing Test Script
Processes images locally on your laptop for testing.
Uses multiprocessing instead of Spark for parallel processing.
"""

import sys
import json
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image
import cv2
import io
import tensorflow as tf
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from tqdm import tqdm
import argparse
import os
import glob


# Import ImageProcessor from dataproc_job (reuse the same class)
# We'll copy it here to avoid import issues
class ImageProcessor:
    """Handles image processing transformations."""

    def __init__(self, config: dict):
        """Initialize processor with configuration."""
        self.config = config
        self.img_config = config.get("image_processing", {})
        self.norm_config = self.img_config.get("normalization", {})
        self.aug_config = self.img_config.get("augmentation", {})
        self.denoise_config = self.img_config.get("denoising", {})
        self.target_size = (
            self.img_config.get("target_width", 224),
            self.img_config.get("target_height", 224)
        )

    def decode_image(self, image_bytes: bytes) -> np.ndarray:
        """Decode image from bytes to numpy array."""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return np.array(image)
        except Exception as e:
            raise ValueError(f"Failed to decode image: {e}")

    def resize_image(self, image: np.ndarray) -> np.ndarray:
        """Resize image to target dimensions."""
        return cv2.resize(image, self.target_size, interpolation=cv2.INTER_AREA)

    def normalize_image(self, image: np.ndarray) -> np.ndarray:
        """Normalize image based on configuration."""
        method = self.norm_config.get("method", "min_max")

        if method == "min_max":
            min_val = self.norm_config.get("min_value", 0.0)
            max_val = self.norm_config.get("max_value", 1.0)
            image = image.astype(np.float32)
            image = (image - image.min()) / (image.max() - image.min() + 1e-8)
            image = image * (max_val - min_val) + min_val
        elif method == "z_score":
            image = image.astype(np.float32)
            mean = image.mean()
            std = image.std() + 1e-8
            image = (image - mean) / std

        return image.astype(np.float32)

    def convert_color_space(self, image: np.ndarray) -> np.ndarray:
        """Convert color space if needed."""
        color_space = self.img_config.get("color_space", "RGB")
        if color_space == "GRAYSCALE":
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                image = np.expand_dims(image, axis=-1)
        return image

    def augment_image(self, image: np.ndarray) -> List[np.ndarray]:
        """Apply data augmentation."""
        if not self.aug_config.get("enabled", False):
            return [image]

        augmented = [image]
        num_augmentations = self.aug_config.get("augmentation_factor", 2)

        for _ in range(num_augmentations):
            aug_image = image.copy()

            # Rotation
            if self.aug_config.get("rotation_range", 0) > 0:
                angle = np.random.uniform(
                    -self.aug_config["rotation_range"],
                    self.aug_config["rotation_range"]
                )
                h, w = aug_image.shape[:2]
                M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
                aug_image = cv2.warpAffine(aug_image, M, (w, h))

            # Horizontal flip
            if self.aug_config.get("horizontal_flip", False) and np.random.random() > 0.5:
                aug_image = cv2.flip(aug_image, 1)

            # Vertical flip
            if self.aug_config.get("vertical_flip", False) and np.random.random() > 0.5:
                aug_image = cv2.flip(aug_image, 0)

            # Brightness adjustment
            if "brightness_range" in self.aug_config:
                brightness = np.random.uniform(
                    *self.aug_config["brightness_range"])
                aug_image = (aug_image * brightness).clip(0,
                                                          255).astype(np.uint8)

            augmented.append(aug_image)

        return augmented

    def denoise_image(self, image: np.ndarray) -> np.ndarray:
        """Apply denoising if enabled."""
        if not self.denoise_config.get("enabled", False):
            return image

        method = self.denoise_config.get("method", "gaussian")
        kernel_size = self.denoise_config.get("kernel_size", 3)

        if method == "gaussian":
            return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
        elif method == "median":
            return cv2.medianBlur(image, kernel_size)

        return image

    def extract_features(self, image: np.ndarray) -> Optional[Dict]:
        """Extract features for classical ML (optional)."""
        feat_config = self.img_config.get("feature_extraction", {})
        if not feat_config.get("enabled", False):
            return None

        features = {}
        methods = feat_config.get("methods", [])

        if "histogram" in methods:
            if len(image.shape) == 3:
                for i in range(image.shape[2]):
                    hist = cv2.calcHist([image], [i], None, [256], [0, 256])
                    features[f"histogram_channel_{i}"] = hist.flatten(
                    ).tolist()
            else:
                hist = cv2.calcHist([image], [0], None, [256], [0, 256])
                features["histogram"] = hist.flatten().tolist()

        return features

    def process_image(
        self,
        image_bytes: bytes,
        label: int,
        image_path: str
    ) -> List[Dict]:
        """
        Process a single image through all transformation steps.

        Returns list of processed images (including augmentations).
        """
        try:
            # Step 1: Image Acquisition (already have bytes)
            # Step 2: Decode
            image = self.decode_image(image_bytes)

            # Step 3: Resize
            image = self.resize_image(image)

            # Step 4: Color Space Conversion
            image = self.convert_color_space(image)

            # Step 5: Denoising (before augmentation)
            image = self.denoise_image(image)

            # Step 6: Normalization
            image = self.normalize_image(image)

            # Step 7: Feature Extraction (optional)
            features = self.extract_features(image)

            # Step 8: Data Augmentation
            augmented_images = self.augment_image(image)

            # Step 9: Flattening (for some ML models)
            flattened = [img.flatten() for img in augmented_images]

            # Step 10: Create records
            records = []
            for idx, (aug_img, flat_img) in enumerate(zip(augmented_images, flattened)):
                record = {
                    "image_array": aug_img.tolist(),
                    "image_flattened": flat_img.tolist(),
                    "label": label,
                    "image_path": image_path,
                    "augmentation_index": idx,
                    "image_shape": list(aug_img.shape),
                    "features": features if features else None
                }
                records.append(record)

            return records

        except Exception as e:
            print(f"Error processing image {image_path}: {e}", file=sys.stderr)
            return []


def extract_label(path: str, label_encoding: dict) -> int:
    """Extract label from file path."""
    path_upper = path.upper()
    if "NORMAL" in path_upper:
        return label_encoding.get("NORMAL", 0)
    elif "PNEUMONIA" in path_upper:
        return label_encoding.get("PNEUMONIA", 1)
    return -1


def extract_split(path: str) -> str:
    """Extract split (train/val/test) from path."""
    if "/train/" in path or "\\train\\" in path:
        return "train"
    elif "/val/" in path or "/validation/" in path or "\\val\\" in path or "\\validation\\" in path:
        return "validation"
    elif "/test/" in path or "\\test\\" in path:
        return "test"
    return "unknown"


def process_single_image(args_tuple):
    """Process a single image file. Used for multiprocessing."""
    file_path, config, label_encoding = args_tuple
    try:
        # Read image file
        with open(file_path, 'rb') as f:
            image_bytes = f.read()

        # Extract label and split
        label = extract_label(str(file_path), label_encoding)
        if label < 0:
            return None

        split = extract_split(str(file_path))

        # Process image
        processor = ImageProcessor(config)
        records = processor.process_image(image_bytes, label, str(file_path))

        # Add split to each record
        for record in records:
            record["split"] = split

        return records
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return None


def create_tfrecord_example(record: dict) -> bytes:
    """Create TFRecord Example from record."""
    def _bytes_feature(value):
        if isinstance(value, type(tf.constant(0))):
            value = value.numpy()
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

    """Returns an int64_list from a bool / enum / int / uint / list."""
    def _int64_feature(value):
        # If it's a single value, wrap it in a list. 
        # If it's already a list (like image_shape), use it as is.
        if not isinstance(value, (list, tuple)):
            value = [value]
        return tf.train.Feature(int64_list=tf.train.Int64List(value=value))
    
    
    image_array = np.array(record["image_array"], dtype=np.float32)
    image_bytes = image_array.tobytes()

    feature = {
        "image": _bytes_feature(image_bytes),
        "label": _int64_feature(record["label"]),
        "image_shape": _int64_feature(record["image_shape"]),
        "image_path": _bytes_feature(record["image_path"].encode()),
    }

    example = tf.train.Example(features=tf.train.Features(feature=feature))
    return example.SerializeToString()


def process_images_local(
    raw_dir: str,
    output_dir: str,
    config: dict,
    num_workers: int = 4,
    max_images: Optional[int] = None
):
    """Main local processing function."""
    processor = ImageProcessor(config)
    label_encoding = config.get(
        "label_encoding", {"NORMAL": 0, "PNEUMONIA": 1})

    # Find all image files
    print(f"Scanning for images in {raw_dir}...")
    image_extensions = ['*.jpeg', '*.jpg', '*.png', '*.JPEG', '*.JPG', '*.PNG']
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(
            raw_dir, '**', ext), recursive=True))
        image_files.extend(
            glob.glob(os.path.join(raw_dir, ext), recursive=False))

    if not image_files:
        raise ValueError(f"No image files found in {raw_dir}")

    print(f"Found {len(image_files)} image files")

    # Limit number of images for testing
    if max_images:
        image_files = image_files[:max_images]
        print(
            f"Processing first {len(image_files)} images (limited for testing)")

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    parquet_dir = os.path.join(output_dir, "parquet")
    tfrecord_dir = os.path.join(output_dir, "tfrecords")

    # Process images in parallel
    print(f"Processing images with {num_workers} workers...")
    all_records = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_single_image, (f, config, label_encoding)): f
            for f in image_files
        }

        # Collect results with progress bar
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            result = future.result()
            if result:
                all_records.extend(result)

    if not all_records:
        raise ValueError("No images were successfully processed")

    print(f"Successfully processed {len(all_records)} image records")

    # Convert to DataFrame
    print("Converting to DataFrame...")
    df = pd.DataFrame(all_records)

    # Write Parquet format
    if config.get("output_formats", {}).get("parquet", {}).get("enabled", True):
        print("Writing Parquet files...")
        os.makedirs(parquet_dir, exist_ok=True)

        # Write by split
        for split in df['split'].unique():
            split_df = df[df['split'] == split]
            split_dir = os.path.join(parquet_dir, f"split={split}")
            os.makedirs(split_dir, exist_ok=True)

            # Convert to PyArrow table
            table = pa.Table.from_pandas(split_df, preserve_index=False)

            # Write parquet file
            output_file = os.path.join(split_dir, f"{split}.parquet")
            pq.write_table(
                table,
                output_file,
                compression=config.get("output_formats", {}).get(
                    "parquet", {}).get("compression", "snappy")
            )
            print(f"  Written {len(split_df)} records to {output_file}")

    # Write TFRecord format
    if config.get("output_formats", {}).get("tfrecord", {}).get("enabled", True):
        print("Writing TFRecord files...")
        os.makedirs(tfrecord_dir, exist_ok=True)

        # Write by split
        for split in df['split'].unique():
            split_df = df[df['split'] == split]
            split_dir = os.path.join(tfrecord_dir, split)
            os.makedirs(split_dir, exist_ok=True)

            # Write TFRecord file
            output_file = os.path.join(split_dir, f"{split}.tfrecord")
            with tf.io.TFRecordWriter(output_file) as writer:
                for _, row in split_df.iterrows():
                    record = {
                        "image_array": row["image_array"],
                        "label": row["label"],
                        "image_path": row["image_path"],
                        "image_shape": row["image_shape"]
                    }
                    example = create_tfrecord_example(record)
                    writer.write(example)

            print(f"  Written {len(split_df)} records to {output_file}")

    # Generate and save metadata
    print("Generating metadata...")
    metadata = {
        "version": config.get("versioning", {}).get("version_tag", "v1.0"),
        "total_images": len(image_files),
        "processed_images": len(all_records),
        "splits": df.groupby("split").size().to_dict(),
        "labels": df.groupby("label").size().to_dict(),
        "config": config,
        "image_shape": processor.target_size,
        "processing_parameters": {
            "normalization": processor.norm_config,
            "augmentation": processor.aug_config,
            "denoising": processor.denoise_config
        }
    }

    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print("Processing complete!")
    print(f"Metadata saved to {metadata_path}")
    print(f"\nOutput summary:")
    print(f"  Total images processed: {len(image_files)}")
    print(f"  Total records (with augmentation): {len(all_records)}")
    print(f"  Parquet files: {parquet_dir}")
    print(f"  TFRecord files: {tfrecord_dir}")
    print(f"  Metadata: {metadata_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process images locally for testing")
    parser.add_argument(
        "--raw-dir",
        type=str,
        required=True,
        help="Local directory path to raw images"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Local directory path for processed output"
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/pipeline_config.yaml",
        help="Local path to pipeline_config.yaml (default: config/pipeline_config.yaml)"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Maximum number of images to process (for testing, default: all)"
    )
    args = parser.parse_args()
    print(f"args: {args}")

    # Load configuration
    if os.path.exists(args.config_path):
        with open(args.config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"Loaded configuration from {args.config_path}")
    else:
        print(
            f"Warning: Config file not found at {args.config_path}, using defaults")
        config = {
            "image_processing": {
                "target_width": 224,
                "target_height": 224,
                "normalization": {"method": "min_max"},
                "augmentation": {"enabled": True, "augmentation_factor": 2}
            },
            "label_encoding": {"NORMAL": 0, "PNEUMONIA": 1},
            "output_formats": {
                "tfrecord": {"enabled": True},
                "parquet": {"enabled": True}
            }
        }

    # Validate directories
    if not os.path.exists(args.raw_dir):
        raise ValueError(f"Raw directory does not exist: {args.raw_dir}")

    # Process images
    process_images_local(
        args.raw_dir,
        args.output_dir,
        config,
        num_workers=args.num_workers,
        max_images=args.max_images
    )


if __name__ == "__main__":
    main()
