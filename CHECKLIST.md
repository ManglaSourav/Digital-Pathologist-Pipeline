# Manual Setup Checklist

Use this checklist to track your progress through the manual setup process.

## Pre-Setup

- [ ] Google Cloud SDK installed (`gcloud --version`)
- [ ] Python 3.8+ installed (`python3 --version`)
- [ ] Authenticated with GCP (`gcloud auth login`)
- [ ] Application default credentials set (`gcloud auth application-default login`)

## Step 1: GCP Project Setup

- [ ] Created/selected GCP project
- [ ] Project ID noted: `_________________`
- [ ] Enabled Cloud Storage API
- [ ] Enabled Dataproc API
- [ ] Enabled Cloud Resource Manager API
- [ ] Billing enabled on project

## Step 2: Create GCS Buckets

- [ ] Created raw data bucket: `gs://_________________-chest-xray-raw`
- [ ] Created processed data bucket: `gs://_________________-chest-xray-processed`
- [ ] Created DVC bucket (optional): `gs://_________________-chest-xray-dvc`
- [ ] Enabled versioning on buckets (optional)
- [ ] Verified buckets exist: `gsutil ls`

## Step 3: Upload Configuration

- [ ] Updated `config/gcp_config.yaml` with project ID
- [ ] Created `config/` folder in processed bucket
- [ ] Uploaded `pipeline_config.yaml` to GCS
- [ ] Verified: `gsutil ls gs://...-processed/config/`

## Step 4: Upload Scripts

- [ ] Created `scripts/` folder in processed bucket
- [ ] Uploaded `dataproc_job.py` to GCS
- [ ] Verified: `gsutil ls gs://...-processed/scripts/`

## Step 5: Upload Raw Data

- [ ] Uploaded training data: `gs://...-raw/raw/v1.0/train/`
- [ ] Uploaded validation data: `gs://...-raw/raw/v1.0/val/`
- [ ] Uploaded test data: `gs://...-raw/raw/v1.0/test/`
- [ ] Verified file counts match local data
- [ ] Verified in Console: Raw bucket contains images

## Step 6: Create Dataproc Cluster

- [ ] Cluster name decided: `chest-xray-processing-cluster`
- [ ] Region selected: `us-central1`
- [ ] Machine types selected (master: n1-standard-4, workers: n1-standard-4)
- [ ] Number of workers: `2`
- [ ] Cluster created successfully
- [ ] Cluster status: `RUNNING`
- [ ] Cluster web interfaces accessible

## Step 7: Submit Dataproc Job

- [ ] Job arguments prepared:
  - Raw GCS path: `gs://_________________/raw/v1.0`
  - Output GCS path: `gs://_________________/processed/v1.0`
  - Config GCS path: `gs://_________________/config/pipeline_config.yaml`
- [ ] Job submitted via Console or CLI
- [ ] Job ID noted: `_________________`

## Step 8: Monitor Job

- [ ] Job status checked in Console
- [ ] Job logs reviewed
- [ ] Spark UI accessed (optional)
- [ ] No errors in logs
- [ ] Job completed successfully

## Step 9: Verify Results

- [ ] Processed data folder exists: `processed/v1.0/`
- [ ] Parquet files created: `parquet/train/`, `parquet/val/`, `parquet/test/`
- [ ] Metadata file exists: `metadata.json`
- [ ] Metadata downloaded and reviewed
- [ ] File counts verified
- [ ] Data quality checked

## Step 10: Cleanup

- [ ] Cluster stopped (if keeping for reuse)
- [ ] OR Cluster deleted (if not needed)
- [ ] Costs reviewed in GCP Console
- [ ] Results downloaded locally (if needed)

## Notes

Project ID: `_________________`
Region: `_________________`
Cluster Name: `_________________`
Job ID: `_________________`
Date Completed: `_________________`

---

## Quick Command Reference

```bash
# Set variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export CLUSTER_NAME="chest-xray-processing-cluster"

# Create cluster
gcloud dataproc clusters create ${CLUSTER_NAME} \
  --region=${REGION} \
  --num-workers=2 \
  --worker-machine-type=n1-standard-4

# Submit job
gcloud dataproc jobs submit pyspark \
  gs://${PROJECT_ID}-chest-xray-processed/scripts/dataproc_job.py \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION} \
  -- \
  --raw-gcs-path=gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0 \
  --output-gcs-path=gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0 \
  --config-gcs-path=gs://${PROJECT_ID}-chest-xray-processed/config/pipeline_config.yaml

# Monitor
gcloud dataproc jobs list --cluster=${CLUSTER_NAME} --region=${REGION}

# Stop cluster
gcloud dataproc clusters stop ${CLUSTER_NAME} --region=${REGION}

# Delete cluster
gcloud dataproc clusters delete ${CLUSTER_NAME} --region=${REGION}
```

