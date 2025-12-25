# Quick Start Guide

This guide will help you run the image processing pipeline step by step.

## Prerequisites Check

```bash
# Verify Python version (3.8+)
python3 --version

# Verify gcloud is installed
gcloud --version

# Verify DVC is installed
dvc --version
```

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure GCP

### 2.1 Set up GCP Project

```bash
# Set your GCP project
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID

# Authenticate
gcloud auth application-default login
```

### 2.2 Create GCS Buckets

```bash
# Create buckets
gsutil mb -l us-central1 gs://${GCP_PROJECT_ID}-chest-xray-raw
gsutil mb -l us-central1 gs://${GCP_PROJECT_ID}-chest-xray-processed
gsutil mb -l us-central1 gs://${GCP_PROJECT_ID}-chest-xray-dvc

# Enable versioning (optional)
gsutil versioning set on gs://${GCP_PROJECT_ID}-chest-xray-raw
gsutil versioning set on gs://${GCP_PROJECT_ID}-chest-xray-processed
```

### 2.3 Update Configuration Files

Edit `config/gcp_config.yaml`:
```yaml
gcp:
  project_id: "your-project-id"  # Replace this
  region: "us-central1"
  
gcs:
  raw_bucket: "gs://your-project-id-chest-xray-raw"  # Replace this
  processed_bucket: "gs://your-project-id-chest-xray-processed"  # Replace this
```

## Step 3: Initialize DVC

```bash
# Initialize DVC (if not already done)
dvc init

# Add GCS remote
dvc remote add -d gcs-remote gs://${GCP_PROJECT_ID}-chest-xray-dvc

# Verify configuration
dvc remote list
```

## Step 4: Upload Raw Data to GCS

```bash
# Upload training data
python scripts/upload_to_gcs.py \
  --local-dir ./train \
  --gcs-bucket gs://${GCP_PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/train \
  --extensions .jpeg .jpg

# Upload validation data
python scripts/upload_to_gcs.py \
  --local-dir ./val \
  --gcs-bucket gs://${GCP_PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/val \
  --extensions .jpeg .jpg

# Upload test data
python scripts/upload_to_gcs.py \
  --local-dir ./test \
  --gcs-bucket gs://${GCP_PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/test \
  --extensions .jpeg .jpg
```

## Step 5: Upload Processing Scripts to GCS

```bash
# Upload the processing script and config
gsutil cp scripts/dataproc_job.py gs://${GCP_PROJECT_ID}-chest-xray-processed/scripts/
gsutil cp config/pipeline_config.yaml gs://${GCP_PROJECT_ID}-chest-xray-processed/config/
```

## Step 6: Run the Pipeline

You have three options to run the pipeline:

### Option A: Run via Dataproc (Recommended for Testing)

```bash
# Create a Dataproc cluster
gcloud dataproc clusters create chest-xray-processing-cluster \
  --region=us-central1 \
  --zone=us-central1-a \
  --master-machine-type=n1-standard-4 \
  --master-boot-disk-size=100 \
  --num-workers=2 \
  --worker-machine-type=n1-standard-4 \
  --worker-boot-disk-size=100 \
  --image-version=2.0-debian10 \
  --project=${GCP_PROJECT_ID}

# Submit the job
gcloud dataproc jobs submit pyspark \
  --cluster=chest-xray-processing-cluster \
  --region=us-central1 \
  --py-files=gs://${GCP_PROJECT_ID}-chest-xray-processed/scripts/dataproc_job.py \
  -- \
  --raw-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-raw/raw/v1.0 \
  --output-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0 \
  --config-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-processed/config/pipeline_config.yaml

# Monitor the job
# Check status in GCP Console: Dataproc > Jobs
# Or use: gcloud dataproc jobs list --cluster=chest-xray-processing-cluster --region=us-central1

# Delete cluster when done (to save costs)
gcloud dataproc clusters delete chest-xray-processing-cluster \
  --region=us-central1 \
  --quiet
```

### Option B: Run via Airflow/Composer (Production)

1. **Create Composer Environment** (one-time setup):
```bash
gcloud composer environments create chest-xray-composer \
  --location us-central1 \
  --python-version 3 \
  --image-version composer-2.0.0-airflow-2.5.0 \
  --project=${GCP_PROJECT_ID}
```

2. **Get DAG folder path**:
```bash
gcloud composer environments describe chest-xray-composer \
  --location us-central1 \
  --format="value(config.dagGcsPrefix)"
```

3. **Upload DAG**:
```bash
DAG_FOLDER=$(gcloud composer environments describe chest-xray-composer \
  --location us-central1 \
  --format="value(config.dagGcsPrefix)")

gsutil cp dags/image_processing_pipeline.py ${DAG_FOLDER}/
```

4. **Set Airflow Variables** (via Airflow UI):
   - Go to Airflow UI (URL from Composer environment)
   - Admin → Variables
   - Add these variables:
     - `gcp_project_id`: your-project-id
     - `raw_bucket`: gs://your-project-id-chest-xray-raw
     - `processed_bucket`: gs://your-project-id-chest-xray-processed
     - `dataproc_cluster_name`: chest-xray-processing-cluster
     - `gcp_region`: us-central1
     - `version_tag`: v1.0

5. **Trigger DAG**:
   - In Airflow UI, find `chest_xray_image_processing_pipeline`
   - Enable and trigger the DAG

### Option C: Local Testing (Small Dataset Only)

For testing with a small subset of data:

```bash
# Create a test script (test_local.py)
cat > test_local.py << 'EOF'
from pyspark.sql import SparkSession
import yaml

# Load config
with open('config/pipeline_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create Spark session
spark = SparkSession.builder \
    .appName("ImageProcessingTest") \
    .master("local[4]") \
    .config("spark.driver.memory", "4g") \
    .getOrCreate()

# Import and run processing
from scripts.dataproc_job import process_images_spark

process_images_spark(
    spark,
    "gs://YOUR_BUCKET/raw/v1.0",  # Update this
    "gs://YOUR_BUCKET/processed/v1.0",  # Update this
    config
)

spark.stop()
EOF

# Run (requires local Spark setup)
# python test_local.py
```

## Step 7: Verify Output

```bash
# Check processed data in GCS
gsutil ls -r gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0/

# Check metadata
gsutil cat gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0/metadata.json
```

## Step 8: Version the Data with DVC

```bash
# After processing, version your data
python scripts/dvc_versioning.py \
  --data-path data/processed/v1.0 \
  --version-tag v1.0 \
  --remote-url gs://${GCP_PROJECT_ID}-chest-xray-dvc

# Or manually
dvc add data/processed/v1.0
dvc push
git add data/processed/v1.0.dvc .dvc/config
git commit -m "Version v1.0 processed data"
git tag v1.0
```

## Step 9: Convert to TFRecord (Optional)

If you need TFRecord format (Spark doesn't write TFRecord natively):

```bash
python scripts/convert_to_tfrecord.py \
  --parquet-path gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0/parquet \
  --output-path ./tfrecords/v1.0 \
  --split train
```

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   # Ensure service account has proper roles
   gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
     --member="serviceAccount:YOUR_SERVICE_ACCOUNT@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   ```

2. **Cluster Creation Fails**:
   - Check quota limits: `gcloud compute project-info describe --project=${GCP_PROJECT_ID}`
   - Try a different region

3. **Out of Memory**:
   - Increase executor memory in `config/pipeline_config.yaml`
   - Use larger machine types

4. **DVC Push Fails**:
   - Verify GCS bucket exists and is accessible
   - Check credentials: `gcloud auth application-default print-access-token`

## Quick Test Command

For a quick end-to-end test with a small dataset:

```bash
# 1. Upload small test dataset
python scripts/upload_to_gcs.py \
  --local-dir ./val \
  --gcs-bucket gs://${GCP_PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0-test/val

# 2. Run processing
gcloud dataproc jobs submit pyspark \
  --cluster=chest-xray-processing-cluster \
  --region=us-central1 \
  --py-files=gs://${GCP_PROJECT_ID}-chest-xray-processed/scripts/dataproc_job.py \
  -- \
  --raw-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-raw/raw/v1.0-test \
  --output-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0-test \
  --config-gcs-path=gs://${GCP_PROJECT_ID}-chest-xray-processed/config/pipeline_config.yaml

# 3. Check results
gsutil ls gs://${GCP_PROJECT_ID}-chest-xray-processed/processed/v1.0-test/
```

## Next Steps

- Review processed data quality
- Adjust processing parameters in `config/pipeline_config.yaml`
- Train ML models using the processed data
- Set up scheduled runs via Airflow

For detailed information, see [README.md](README.md).

