# Manual Setup and Execution Guide

This guide walks you through setting up and running the image processing pipeline **manually** using the GCP Console and command line. This is perfect for understanding each step before automating with Airflow.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [GCP Project Setup](#2-gcp-project-setup)
3. [Create GCS Buckets](#3-create-gcs-buckets)
4. [Upload Configuration Files](#4-upload-configuration-files)
5. [Upload Processing Scripts](#5-upload-processing-scripts)
6. [Upload Raw Image Data](#6-upload-raw-image-data)
7. [Create Dataproc Cluster](#7-create-dataproc-cluster)
8. [Submit Dataproc Job](#8-submit-dataproc-job)
9. [Monitor Job Execution](#9-monitor-job-execution)
10. [Verify Results](#10-verify-results)
11. [Stop/Delete Cluster](#11-stopdelete-cluster)

---

## 1. Prerequisites

### 1.1 Install Required Tools

```bash
# Install Google Cloud SDK (if not already installed)
# macOS:
brew install --cask google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install

# Verify installation
gcloud --version
```

### 1.2 Authenticate with GCP

```bash
# Login to GCP
gcloud auth login

# Set default application credentials
gcloud auth application-default login

# Verify authentication
gcloud auth list
```

### 1.3 Install Python Dependencies

```bash
# Navigate to project directory
cd /Users/souravmangla/Desktop/chest_xray

# Install dependencies
pip install -r requirements.txt
```

---

## 2. GCP Project Setup

### 2.1 Create or Select GCP Project

**Option A: Using Console**
1. Go to [GCP Console](https://console.cloud.google.com/)
2. Click on project dropdown (top bar)
3. Click "New Project"
4. Enter project name: `chest-xray-processing`
5. Click "Create"
6. Wait for project creation (30-60 seconds)

**Option B: Using gcloud CLI**
```bash
# Create new project
gcloud projects create chest-xray-processing --name="Chest X-ray Processing"

# Set as current project
gcloud config set project chest-xray-processing

# Enable billing (required for Dataproc)
# Note: You'll need to do this in Console or use billing account ID
```

### 2.2 Enable Required APIs

**Using Console:**
1. Go to [APIs & Services > Library](https://console.cloud.google.com/apis/library)
2. Enable these APIs (search and click "Enable"):
   - **Cloud Storage API**
   - **Cloud Dataproc API**
   - **Cloud Composer API** (if using Airflow later)
   - **Cloud Resource Manager API**

**Using gcloud CLI:**
```bash
# Set your project ID (replace with your actual project ID)
export PROJECT_ID="chest-xray-processing"

# Enable APIs
gcloud services enable storage-component.googleapis.com
gcloud services enable dataproc.googleapis.com
gcloud services enable composer.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

### 2.3 Set Project Variables

```bash
# Set environment variable for easy reference
export PROJECT_ID="chest-xray-processing"  # Replace with your project ID
export REGION="us-central1"
export ZONE="us-central1-a"

# Set in gcloud config
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE

# Verify
gcloud config list
```

---

## 3. Create GCS Buckets

### 3.1 Create Buckets Using Console

1. Go to [Cloud Storage > Buckets](https://console.cloud.google.com/storage/browser)
2. Click "Create Bucket"
3. **Bucket 1: Raw Data**
   - Name: `{PROJECT_ID}-chest-xray-raw` (e.g., `chest-xray-processing-chest-xray-raw`)
   - Location type: **Region**
   - Location: **us-central1**
   - Storage class: **Standard**
   - Access control: **Uniform**
   - Click "Create"

4. **Bucket 2: Processed Data**
   - Name: `{PROJECT_ID}-chest-xray-processed`
   - Same settings as above
   - Click "Create"

5. **Bucket 3: DVC Remote (Optional)**
   - Name: `{PROJECT_ID}-chest-xray-dvc`
   - Same settings as above
   - Click "Create"

### 3.2 Create Buckets Using gcloud CLI

```bash
# Create raw data bucket
gsutil mb -l us-central1 gs://${PROJECT_ID}-chest-xray-raw

# Create processed data bucket
gsutil mb -l us-central1 gs://${PROJECT_ID}-chest-xray-processed

# Create DVC bucket (optional)
gsutil mb -l us-central1 gs://${PROJECT_ID}-chest-xray-dvc

# Verify buckets created
gsutil ls
```

### 3.3 Enable Versioning (Optional but Recommended)

**Using Console:**
1. Click on each bucket
2. Go to "Configuration" tab
3. Under "Object versioning", click "Edit"
4. Select "Enable"
5. Click "Save"

**Using CLI:**
```bash
# Enable versioning on all buckets
gsutil versioning set on gs://${PROJECT_ID}-chest-xray-raw
gsutil versioning set on gs://${PROJECT_ID}-chest-xray-processed
gsutil versioning set on gs://${PROJECT_ID}-chest-xray-dvc
```

### 3.4 Verify Bucket Structure

```bash
# List all buckets
gsutil ls

# Expected output:
# gs://chest-xray-processing-chest-xray-dvc/
# gs://chest-xray-processing-chest-xray-processed/
# gs://chest-xray-processing-chest-xray-raw/
```

---

## 4. Upload Configuration Files

### 4.1 Update Configuration Files Locally

First, edit the configuration files with your project details:

```bash
# Edit GCP config
nano config/gcp_config.yaml
# Or use your preferred editor
```

Update these values in `config/gcp_config.yaml`:
```yaml
gcp:
  project_id: "chest-xray-processing"  # Your actual project ID
  region: "us-central1"
  zone: "us-central1-a"

gcs:
  raw_bucket: "gs://chest-xray-processing-chest-xray-raw"
  processed_bucket: "gs://chest-xray-processing-chest-xray-processed"
  staging_bucket: "gs://chest-xray-processing-chest-xray-staging"
```

### 4.2 Create Directory Structure in GCS

```bash
# Create directory structure in processed bucket
gsutil -m mkdir gs://${PROJECT_ID}-chest-xray-processed/config
gsutil -m mkdir gs://${PROJECT_ID}-chest-xray-processed/scripts
```

### 4.3 Upload Configuration Files

```bash
# Upload pipeline configuration
gsutil cp config/pipeline_config.yaml \
  gs://${PROJECT_ID}-chest-xray-processed/config/pipeline_config.yaml

# Verify upload
gsutil ls gs://${PROJECT_ID}-chest-xray-processed/config/
```

**Expected output:**
```
gs://chest-xray-processing-chest-xray-processed/config/pipeline_config.yaml
```

### 4.4 Verify in Console

1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click on `{PROJECT_ID}-chest-xray-processed` bucket
3. Navigate to `config/` folder
4. Verify `pipeline_config.yaml` is present

---

## 5. Upload Processing Scripts

### 5.1 Upload Dataproc Processing Script

```bash
# Upload the main processing script
gsutil cp scripts/dataproc_job.py \
  gs://${PROJECT_ID}-chest-xray-processed/scripts/dataproc_job.py

# Verify upload
gsutil ls gs://${PROJECT_ID}-chest-xray-processed/scripts/
```

**Expected output:**
```
gs://chest-xray-processing-chest-xray-processed/scripts/dataproc_job.py
```

### 5.2 Verify Script in Console

1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click on `{PROJECT_ID}-chest-xray-processed` bucket
3. Navigate to `scripts/` folder
4. Verify `dataproc_job.py` is present

---

## 6. Upload Raw Image Data

### 6.1 Prepare Local Data Structure

Your local structure should look like:
```
chest_xray/
├── train/
│   ├── NORMAL/
│   └── PNEUMONIA/
├── val/
│   ├── NORMAL/
│   └── PNEUMONIA/
└── test/
    ├── NORMAL/
    └── PNEUMONIA/
```

### 6.2 Upload Using Python Script (Recommended)

```bash
# Upload training data
python scripts/upload_to_gcs.py \
  --local-dir ./train \
  --gcs-bucket gs://${PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/train \
  --extensions .jpeg .jpg

# Upload validation data
python scripts/upload_to_gcs.py \
  --local-dir ./val \
  --gcs-bucket gs://${PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/val \
  --extensions .jpeg .jpg

# Upload test data
python scripts/upload_to_gcs.py \
  --local-dir ./test \
  --gcs-bucket gs://${PROJECT_ID}-chest-xray-raw \
  --gcs-prefix raw/v1.0/test \
  --extensions .jpeg .jpg
```

### 6.3 Upload Using gsutil (Alternative)

```bash
# Upload training data
gsutil -m cp -r ./train/* \
  gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/train/

# Upload validation data
gsutil -m cp -r ./val/* \
  gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/val/

# Upload test data
gsutil -m cp -r ./test/* \
  gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/test/
```

### 6.4 Verify Upload

```bash
# Count files in each split
gsutil ls -r gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/train/ | wc -l
gsutil ls -r gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/val/ | wc -l
gsutil ls -r gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/test/ | wc -l

# List a few files to verify
gsutil ls gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/train/NORMAL/ | head -5
```

### 6.5 Verify in Console

1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click on `{PROJECT_ID}-chest-xray-raw` bucket
3. Navigate to `raw/v1.0/` folder
4. Verify `train/`, `val/`, and `test/` folders exist with images

---

## 7. Create Dataproc Cluster

### 7.1 Create Cluster Using Console

1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Click "Create Cluster"
3. **Cluster Basics:**
   - Cluster name: `chest-xray-processing-cluster`
   - Region: `us-central1`
   - Zone: `us-central1-a` (or leave as "Any zone in region")
   
4. **Cluster Config:**
   - **Master node:**
     - Machine type: `n1-standard-4` (4 vCPU, 15 GB RAM)
     - Disk type: `Standard persistent disk`
     - Disk size: `100 GB`
     - Number of nodes: `1`
   
   - **Worker nodes:**
     - Machine type: `n1-standard-4`
     - Disk type: `Standard persistent disk`
     - Disk size: `100 GB`
     - Number of nodes: `2`
   
5. **Component Gateway:** Enable (for accessing web UIs)
6. **Optional settings:**
   - **Initialization actions:** Leave empty
   - **Advanced options:**
     - **Software Config:**
       - Image version: `2.0-debian10` (or latest)
       - **Properties:**
         - `spark:spark.executor.memory=4g`
         - `spark:spark.executor.cores=2`
         - `spark:spark.driver.memory=2g`

7. Click "Create"
8. Wait for cluster creation (2-5 minutes)

### 7.2 Create Cluster Using gcloud CLI

```bash
# Create cluster
gcloud dataproc clusters create chest-xray-processing-cluster \
  --region=us-central1 \
  --zone=us-central1-a \
  --master-machine-type=n1-standard-4 \
  --master-boot-disk-size=100 \
  --num-workers=2 \
  --worker-machine-type=n1-standard-4 \
  --worker-boot-disk-size=100 \
  --image-version=2.0-debian10 \
  --enable-component-gateway \
  --properties=spark:spark.executor.memory=4g,spark:spark.executor.cores=2,spark:spark.driver.memory=2g \
  --project=${PROJECT_ID}

# Monitor creation
gcloud dataproc clusters describe chest-xray-processing-cluster \
  --region=us-central1
```

### 7.3 Verify Cluster Status

**Using Console:**
1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Check cluster status (should be "Running")

**Using CLI:**
```bash
# List clusters
gcloud dataproc clusters list --region=us-central1

# Get cluster details
gcloud dataproc clusters describe chest-xray-processing-cluster \
  --region=us-central1 \
  --format="yaml(status.state)"
```

**Expected output:**
```
state: RUNNING
```

---

## 8. Submit Dataproc Job

### 8.1 Prepare Job Arguments

Set these variables for easy reference:

```bash
# Set paths
RAW_GCS_PATH="gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0"
OUTPUT_GCS_PATH="gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0"
CONFIG_GCS_PATH="gs://${PROJECT_ID}-chest-xray-processed/config/pipeline_config.yaml"
SCRIPT_GCS_PATH="gs://${PROJECT_ID}-chest-xray-processed/scripts/dataproc_job.py"
CLUSTER_NAME="chest-xray-processing-cluster"
REGION="us-central1"
```

### 8.2 Submit Job Using Console

1. Go to [Dataproc > Jobs](https://console.cloud.google.com/dataproc/jobs)
2. Click "Submit Job"
3. **Job Details:**
   - **Job type:** `PySpark`
   - **Cluster:** Select `chest-xray-processing-cluster` from dropdown
   - **Main Python file:** `gs://chest-xray-processing-chest-xray-processed/scripts/dataproc_job.py`
   
4. **Arguments:**
   ```
   --raw-gcs-path
   gs://chest-xray-processing-chest-xray-raw/raw/v1.0
   --output-gcs-path
   gs://chest-xray-processing-chest-xray-processed/processed/v1.0
   --config-gcs-path
   gs://chest-xray-processing-chest-xray-processed/config/pipeline_config.yaml
   ```
   (Add each argument on a new line)
   
5. **Properties (Optional):**
   ```
   spark.executor.memory=4g
   spark.executor.cores=2
   spark.driver.memory=2g
   spark.sql.shuffle.partitions=200
   ```
   
6. Click "Submit"

### 8.3 Submit Job Using gcloud CLI

```bash
# Submit the job
gcloud dataproc jobs submit pyspark \
  ${SCRIPT_GCS_PATH} \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION} \
  -- \
  --raw-gcs-path=${RAW_GCS_PATH} \
  --output-gcs-path=${OUTPUT_GCS_PATH} \
  --config-gcs-path=${CONFIG_GCS_PATH}

# The job will start running immediately
```

### 8.4 Submit Job with Additional Spark Properties

```bash
# Submit with custom Spark properties
gcloud dataproc jobs submit pyspark \
  ${SCRIPT_GCS_PATH} \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION} \
  --properties=spark.executor.memory=4g,spark.executor.cores=2,spark.driver.memory=2g \
  -- \
  --raw-gcs-path=${RAW_GCS_PATH} \
  --output-gcs-path=${OUTPUT_GCS_PATH} \
  --config-gcs-path=${CONFIG_GCS_PATH}
```

---

## 9. Monitor Job Execution

### 9.1 Monitor Using Console

1. Go to [Dataproc > Jobs](https://console.cloud.google.com/dataproc/jobs)
2. Click on your job to view details
3. **Job Details Tab:**
   - Status: Running/Completed/Failed
   - Start time, duration
   - Cluster information
   
4. **Logs Tab:**
   - View driver logs (main output)
   - View worker logs
   - Filter by log level (INFO, WARN, ERROR)
   
5. **Output Tab:**
   - View job output
   - Check for errors

### 9.2 Monitor Using gcloud CLI

```bash
# List all jobs
gcloud dataproc jobs list \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION}

# Get job status
gcloud dataproc jobs describe JOB_ID \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION}

# Get job logs
gcloud dataproc jobs get-logs JOB_ID \
  --cluster=${CLUSTER_NAME} \
  --region=${REGION}
```

### 9.3 Monitor Using Spark UI

1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Click on your cluster name
3. Click "Web Interfaces" tab
4. Click "Spark History Server" or "YARN ResourceManager"
5. View job progress, stages, and executor status

### 9.4 Check Job Progress in Logs

Look for these log messages:
```
Reading images from gs://...
Processing images...
Writing Parquet files...
Writing TFRecord files...
Generating metadata...
Processing complete!
```

---

## 10. Verify Results

### 10.1 Check Processed Data in Console

1. Go to [Cloud Storage](https://console.cloud.google.com/storage/browser)
2. Click on `{PROJECT_ID}-chest-xray-processed` bucket
3. Navigate to `processed/v1.0/` folder
4. You should see:
   - `parquet/` folder (with train/, val/, test/ subfolders)
   - `tfrecords_intermediate/` folder (if TFRecord was enabled)
   - `metadata.json` file

### 10.2 Verify Using gsutil

```bash
# List processed data structure
gsutil ls -r gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/

# Check metadata
gsutil cat gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/metadata.json

# Count Parquet files
gsutil ls gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/parquet/train/ | wc -l
```

### 10.3 View Metadata

```bash
# Download and view metadata
gsutil cp gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/metadata.json ./metadata.json
cat metadata.json | python -m json.tool
```

**Expected metadata structure:**
```json
{
  "version": "v1.0",
  "total_images": 5216,
  "processed_images": 10432,
  "splits": [...],
  "labels": [...],
  "config": {...},
  "image_shape": [224, 224],
  "processing_parameters": {...}
}
```

### 10.4 Verify Parquet Files

```bash
# List Parquet files
gsutil ls gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/parquet/train/

# Download a sample file to verify (optional)
gsutil cp gs://${PROJECT_ID}-chest-xray-processed/processed/v1.0/parquet/train/part-00000-*.parquet ./sample.parquet
```

---

## 11. Stop/Delete Cluster

### 11.1 Stop Cluster (Keep for Reuse)

**Using Console:**
1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Click on cluster name
3. Click "Stop" button
4. Confirm stop action
5. Wait for cluster to stop (1-2 minutes)

**Using CLI:**
```bash
# Stop cluster
gcloud dataproc clusters stop chest-xray-processing-cluster \
  --region=us-central1

# Verify stopped
gcloud dataproc clusters describe chest-xray-processing-cluster \
  --region=us-central1 \
  --format="yaml(status.state)"
```

**Expected output:**
```
state: STOPPED
```

### 11.2 Start Stopped Cluster

**Using Console:**
1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Click on stopped cluster
3. Click "Start" button
4. Wait for cluster to start (2-3 minutes)

**Using CLI:**
```bash
# Start cluster
gcloud dataproc clusters start chest-xray-processing-cluster \
  --region=us-central1
```

### 11.3 Delete Cluster (Permanent)

**Using Console:**
1. Go to [Dataproc > Clusters](https://console.cloud.google.com/dataproc/clusters)
2. Click on cluster name
3. Click "Delete" button
4. Type cluster name to confirm
5. Click "Delete"
6. Wait for deletion (1-2 minutes)

**Using CLI:**
```bash
# Delete cluster
gcloud dataproc clusters delete chest-xray-processing-cluster \
  --region=us-central1 \
  --quiet

# Verify deletion
gcloud dataproc clusters list --region=us-central1
```

---

## Troubleshooting

### Common Issues

#### 1. **Cluster Creation Fails**
- **Issue:** Quota exceeded
- **Solution:** 
  ```bash
  # Check quotas
  gcloud compute project-info describe --project=${PROJECT_ID}
  
  # Request quota increase in Console: IAM & Admin > Quotas
  ```

#### 2. **Job Fails with "Out of Memory"**
- **Issue:** Not enough executor memory
- **Solution:** Increase memory in cluster config or job properties
  ```bash
  # Recreate cluster with more memory
  gcloud dataproc clusters create ... \
    --properties=spark:spark.executor.memory=8g
  ```

#### 3. **Files Not Found in GCS**
- **Issue:** Incorrect GCS paths
- **Solution:** Verify paths exist
  ```bash
  gsutil ls gs://${PROJECT_ID}-chest-xray-raw/raw/v1.0/
  ```

#### 4. **Permission Denied**
- **Issue:** Service account lacks permissions
- **Solution:** Grant Storage Admin and Dataproc Worker roles
  ```bash
  # Get your service account
  gcloud iam service-accounts list
  
  # Grant roles (replace SERVICE_ACCOUNT_EMAIL)
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.admin"
  ```

#### 5. **Job Stuck in "Running" State**
- **Issue:** Job may be processing large dataset
- **Solution:** 
  - Check Spark UI for progress
  - Review logs for errors
  - Consider increasing cluster size

---

## Quick Reference Commands

```bash
# Set variables
export PROJECT_ID="chest-xray-processing"
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

# Monitor job
gcloud dataproc jobs list --cluster=${CLUSTER_NAME} --region=${REGION}

# Stop cluster
gcloud dataproc clusters stop ${CLUSTER_NAME} --region=${REGION}

# Delete cluster
gcloud dataproc clusters delete ${CLUSTER_NAME} --region=${REGION}
```

---

## Next Steps

After successfully running the pipeline manually:

1. **Review Results:** Check processed data quality and metadata
2. **Optimize Configuration:** Adjust `pipeline_config.yaml` parameters
3. **Set Up Airflow:** Automate the pipeline using Composer (see README.md)
4. **Train ML Models:** Use processed data for model training
5. **Set Up Monitoring:** Configure alerts for job failures

---

## Cost Estimation

**Approximate costs for one run:**
- **Dataproc Cluster:** ~$0.50-2.00/hour (depending on machine types)
- **GCS Storage:** ~$0.020/GB/month
- **Network Egress:** ~$0.12/GB (if downloading results)

**Cost-saving tips:**
- Stop cluster when not in use
- Use preemptible workers (50% cheaper)
- Delete cluster after processing if not needed
- Use lifecycle policies for old data

---

For automated execution, see [README.md](README.md) and [QUICKSTART.md](QUICKSTART.md).

