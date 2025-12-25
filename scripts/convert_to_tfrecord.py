#!/usr/bin/env python3
"""
Convert Parquet files to TFRecord format
Post-processing script to convert Spark-generated Parquet files to TFRecord.
"""

import sys
import argparse
import tensorflow as tf
import pandas as pd
from pathlib import Path
from google.cloud import storage
import pyarrow.parquet as pq
import pyarrow.dataset as ds
from tqdm import tqdm


def create_tfrecord_example(image_array, label, image_path, image_shape):
    """Create a TFRecord Example."""
    def _bytes_feature(value):
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

    def _int64_feature(value):
        return tf.train.Feature(int64_list=tf.train.Int64List(value=value))

    # Convert image array to bytes
    import numpy as np
    if isinstance(image_array, list):
        image_array = np.array(image_array, dtype=np.float32)
    image_bytes = image_array.tobytes()

    feature = {
        "image": _bytes_feature(image_bytes),
        "label": _int64_feature([int(label)]),
        "image_shape": _int64_feature([int(s) for s in image_shape]),
        "image_path": _bytes_feature(str(image_path).encode()),
    }

    example = tf.train.Example(features=tf.train.Features(feature=feature))
    return example.SerializeToString()


def convert_parquet_to_tfrecord(
    parquet_path: str,
    output_path: str,
    split: str = None,
    batch_size: int = 1000
):
    """Convert Parquet files to TFRecord format."""

    # Read Parquet files
    print(f"Reading Parquet files from {parquet_path}")
    dataset = ds.dataset(parquet_path, format="parquet")

    if split:
        dataset = dataset.filter(ds.field("split") == split)

    # Create output directory
    output_path_obj = Path(output_path)
    output_path_obj.mkdir(parents=True, exist_ok=True)

    # Process in batches
    batch_num = 0
    total_records = 0

    for batch in dataset.to_batches(batch_size=batch_size):
        batch_df = batch.to_pandas()

        # Create TFRecord file for this batch
        tfrecord_filename = output_path_obj / f"part-{batch_num:05d}.tfrecord"

        with tf.io.TFRecordWriter(str(tfrecord_filename)) as writer:
            for _, row in tqdm(batch_df.iterrows(), total=len(batch_df), desc=f"Batch {batch_num}"):
                try:
                    example = create_tfrecord_example(
                        row["image_array"],
                        row["label"],
                        row.get("image_path", ""),
                        row["image_shape"]
                    )
                    writer.write(example)
                    total_records += 1
                except Exception as e:
                    print(f"Error processing row: {e}", file=sys.stderr)
                    continue

        print(f"Wrote {len(batch_df)} records to {tfrecord_filename}")
        batch_num += 1

    print(f"Total records converted: {total_records}")
    return total_records


def main():
    parser = argparse.ArgumentParser(description="Convert Parquet to TFRecord")
    parser.add_argument(
        "--parquet-path",
        type=str,
        required=True,
        help="Path to Parquet files (local or GCS)"
    )
    parser.add_argument(
        "--output-path",
        type=str,
        required=True,
        help="Output path for TFRecord files"
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "validation", "test"],
        help="Specific split to convert (optional)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for processing"
    )

    args = parser.parse_args()

    convert_parquet_to_tfrecord(
        args.parquet_path,
        args.output_path,
        args.split,
        args.batch_size
    )


if __name__ == "__main__":
    main()
