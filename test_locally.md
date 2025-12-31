# Testing Image Processing Locally

This guide shows how to run the image processing pipeline locally before deploying to Dataproc.

## Prerequisites

Install required Python packages:

```bash
pip install -r requirements.txt
```

## Basic Usage

```bash
python scripts/test_image_processing_local.py \
  --raw-dir data/raw/v1.0/train \
  --output-dir data/processed/v1.0 \
  --config-path config/pipeline_config.yaml
```

## Command Options

### Required Arguments

- `--raw-dir`: Local directory containing raw images
  - Example: `data/raw/v1.0/train` or `data/train`

- `--output-dir`: Local directory for processed output
  - Example: `data/processed/v1.0`
  - Will be created if it doesn't exist

### Optional Arguments

- `--config-path`: Path to pipeline configuration YAML
  - Default: `config/pipeline_config.yaml`

- `--num-workers`: Number of parallel workers
  - Default: 4
  - Increase for faster processing

- `--max-images`: Limit number of images to process
  - Default: all images
  - Useful for quick testing

## Example Commands

### Process all images

```bash
python scripts/test_image_processing_local.py \
  --raw-dir data/train \
  --output-dir data/processed/v1.0
```

### Process with custom settings

```bash
python scripts/test_image_processing_local.py \
  --raw-dir data/raw/v1.0/train \
  --output-dir data/processed/v1.0 \
  --config-path config/pipeline_config.yaml \
  --num-workers 8 \
  --max-images 100
```

### Quick test with limited images

```bash
python scripts/test_image_processing_local.py \
  --raw-dir data/train \
  --output-dir data/processed/v1.0 \
  --max-images 10 \
  --num-workers 2
```

## Output

The script generates processed files in the output directory:

- **Parquet files**: `{output-dir}/parquet/split={split}/`
- **TFRecord files**: `{output-dir}/tfrecords/{split}/`
- **Metadata**: `{output-dir}/metadata.json`
