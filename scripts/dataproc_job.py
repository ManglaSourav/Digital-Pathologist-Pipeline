#!/usr/bin/env python3
"""
Dataproc Image Processing Job
PySpark script for processing images with all transformation steps.
"""

import sys
import json
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lit, when, rand, explode, array, struct
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    ArrayType, FloatType, BinaryType
)
from PIL import Image
import cv2
import io
import tensorflow as tf
from google.cloud import storage


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

    def flatten_image(self, image: np.ndarray) -> np.ndarray:
        """Flatten image for ML models."""
        return image.flatten()

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


def load_config_from_gcs(gcs_path: str) -> dict:
    """Load configuration from GCS."""
    client = storage.Client()
    bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    content = blob.download_as_text()
    return yaml.safe_load(content)


def create_tfrecord_example(record: dict) -> bytes:
    """Create TFRecord Example from record."""
    def _bytes_feature(value):
        if isinstance(value, type(tf.constant(0))):
            value = value.numpy()
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

    def _int64_feature(value):
        return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

    def _float_feature(value):
        return tf.train.Feature(float_list=tf.train.FloatList(value=value))

    image_array = np.array(record["image_array"], dtype=np.float32)
    image_bytes = image_array.tobytes()

    feature = {
        "image": _bytes_feature(image_bytes),
        "label": _int64_feature([record["label"]]),
        "image_shape": _int64_feature(record["image_shape"]),
        "image_path": _bytes_feature(record["image_path"].encode()),
    }

    example = tf.train.Example(features=tf.train.Features(feature=feature))
    return example.SerializeToString()


def process_images_spark(
    spark: SparkSession,
    raw_gcs_path: str,
    output_gcs_path: str,
    config: dict
):
    """Main Spark processing function."""
    processor = ImageProcessor(config)

    # Load configuration
    label_encoding = config.get(
        "label_encoding", {"NORMAL": 0, "PNEUMONIA": 1})

    # Read images from GCS using binary file format
    print(f"Reading images from {raw_gcs_path}")
    df = spark.read.format("binaryFile").load(f"{raw_gcs_path}/*/*.jpeg")

    # Extract label from path
    def extract_label(path: str) -> int:
        if "NORMAL" in path.upper():
            return label_encoding.get("NORMAL", 0)
        elif "PNEUMONIA" in path.upper():
            return label_encoding.get("PNEUMONIA", 1)
        return -1

    extract_label_udf = udf(extract_label, IntegerType())
    df = df.withColumn("label", extract_label_udf(col("path")))
    df = df.filter(col("label") >= 0)  # Filter out unknown labels

    # Extract split from path (train/val/test)
    def extract_split(path: str) -> str:
        if "/train/" in path:
            return "train"
        elif "/val/" in path or "/validation/" in path:
            return "validation"
        elif "/test/" in path:
            return "test"
        return "unknown"

    extract_split_udf = udf(extract_split, StringType())
    df = df.withColumn("split", extract_split_udf(col("path")))

    # Process images using mapPartitions for better efficiency
    print("Processing images...")

    # Define output schema
    output_schema = StructType([
        StructField("image_array", ArrayType(
            ArrayType(ArrayType(FloatType())))),
        StructField("image_flattened", ArrayType(FloatType())),
        StructField("label", IntegerType()),
        StructField("image_path", StringType()),
        StructField("augmentation_index", IntegerType()),
        StructField("image_shape", ArrayType(IntegerType())),
        StructField("features", StringType()),
        StructField("split", StringType())
    ])

    def process_partition(partition):
        """Process a partition of images."""
        # Create processor instance per partition (avoids serialization issues)
        local_processor = ImageProcessor(config)
        results = []

        for row in partition:
            try:
                records = local_processor.process_image(
                    row.content,
                    row.label,
                    row.path
                )
                # Add split to each record
                for record in records:
                    record["split"] = row.split
                    results.append((
                        record["image_array"],
                        record["image_flattened"],
                        record["label"],
                        record["image_path"],
                        record["augmentation_index"],
                        record["image_shape"],
                        json.dumps(record["features"]
                                   ) if record["features"] else None,
                        record["split"]
                    ))
            except Exception as e:
                print(f"Error processing {row.path}: {e}", file=sys.stderr)
                continue

        return iter(results)

    # Process using mapPartitions
    processed_rdd = df.rdd.mapPartitions(process_partition)
    processed_df = spark.createDataFrame(processed_rdd, schema=output_schema)

    # Repartition for better parallelism
    num_partitions = config.get("processing", {}).get("num_partitions", 200)
    processed_df = processed_df.repartition(num_partitions)

    # Write Parquet format
    if config.get("output_formats", {}).get("parquet", {}).get("enabled", True):
        print("Writing Parquet files...")
        parquet_path = f"{output_gcs_path}/parquet"
        processed_df.write.mode("overwrite").partitionBy("split").parquet(
            parquet_path,
            compression=config.get("output_formats", {}).get(
                "parquet", {}).get("compression", "snappy")
        )

    # Write TFRecord format
    if config.get("output_formats", {}).get("tfrecord", {}).get("enabled", True):
        print("Writing TFRecord files...")
        tfrecord_path = f"{output_gcs_path}/tfrecords"

        # Convert DataFrame rows to TFRecord format
        def create_tfrecord_from_row(row):
            record = {
                "image_array": row.image_array,
                "label": row.label,
                "image_path": row.image_path,
                "image_shape": row.image_shape
            }
            return create_tfrecord_example(record)

        # Use mapPartitions to create TFRecords
        tfrecord_rdd = processed_df.rdd.map(lambda row: (
            create_tfrecord_from_row(row),
            row.split
        ))

        # Convert back to DataFrame for writing
        tfrecord_df = spark.createDataFrame(
            tfrecord_rdd,
            schema=StructType([
                StructField("tfrecord", BinaryType()),
                StructField("split", StringType())
            ])
        )

        # Write TFRecords - need to save as binary files
        # Note: Spark doesn't have native TFRecord writer, so we'll write as Parquet with binary
        # For production, consider using tf.data.Dataset API or separate TFRecord writer
        print("Note: TFRecord writing via Spark has limitations. Consider using TensorFlow's tf.data API for better TFRecord support.")

        # Alternative: Write image arrays and metadata, convert to TFRecord in post-processing
        # For now, we'll write the data in a format that can be easily converted to TFRecord
        tfrecord_df.write.mode("overwrite").partitionBy("split").parquet(
            f"{tfrecord_path}_intermediate"
        )

    # Generate metadata
    print("Generating metadata...")
    metadata = {
        "version": config.get("versioning", {}).get("version_tag", "v1.0"),
        "total_images": df.count(),
        "processed_images": processed_df.count(),
        "splits": processed_df.groupBy("split").count().collect(),
        "labels": processed_df.groupBy("label").count().collect(),
        "config": config,
        "image_shape": processor.target_size,
        "processing_parameters": {
            "normalization": processor.norm_config,
            "augmentation": processor.aug_config,
            "denoising": processor.denoise_config
        }
    }

    # Save metadata to GCS
    metadata_path = f"{output_gcs_path}/metadata.json"
    client = storage.Client()
    bucket_name, blob_path = metadata_path.replace("gs://", "").split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(metadata, indent=2))

    print("Processing complete!")
    print(f"Metadata saved to {metadata_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Process images with Dataproc")
    parser.add_argument(
        "--raw-gcs-path",
        type=str,
        required=True,
        help="GCS path to raw images"
    )
    parser.add_argument(
        "--output-gcs-path",
        type=str,
        required=True,
        help="GCS path for processed output"
    )
    parser.add_argument(
        "--config-gcs-path",
        type=str,
        help="GCS path to pipeline_config.yaml"
    )
    parser.add_argument(
        "--config-local-path",
        type=str,
        help="Local path to pipeline_config.yaml"
    )

    args = parser.parse_args()

    # Load configuration
    if args.config_gcs_path:
        config = load_config_from_gcs(args.config_gcs_path)
    elif args.config_local_path:
        with open(args.config_local_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        # Default config
        config = {
            "image_processing": {
                "target_width": 224,
                "target_height": 224,
                "normalization": {"method": "min_max"},
                "augmentation": {"enabled": True}
            },
            "label_encoding": {"NORMAL": 0, "PNEUMONIA": 1},
            "output_formats": {"tfrecord": {"enabled": True}, "parquet": {"enabled": True}}
        }

    # Initialize Spark
    spark = SparkSession.builder \
        .appName("ImageProcessingPipeline") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()

    try:
        process_images_spark(
            spark,
            args.raw_gcs_path,
            args.output_gcs_path,
            config
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
