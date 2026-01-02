# Chest X-ray Image Processing Pipeline

A production-grade data pipeline for processing chest X-ray images with data versioning capabilities. This pipeline uses Google Cloud Platform services (GCS, Dataproc, Composer, Cloud Build) to transform raw images into ML-ready formats (TFRecord and Parquet) with GCS versioning support.

## Architecture Overview

```
GCS Upload (Raw Bucket)
  ↓
Dataproc Processing (PySpark)
  ├── Resize (224x224)
  ├── Normalize/Scale
  ├── Color Space Conversion
  ├── Data Augmentation
  ├── Denoising (optional)
  ├── Feature Extraction (optional)
  ├── Label Encoding
  ├── Batch Creation
  └── Export (TFRecord & Parquet)
  ↓
GCS Storage (Processed Bucket)
  ↓
GCS Versioning (Object Versioning)
  ↓
Ready for ML Training
```

## Technology Stack

- **Google Cloud Storage (GCS)**: Scalable object storage for raw and processed images with built-in versioning
- **Dataproc**: Spark cluster for distributed image processing
- **Composer (Airflow)**: Managed workflow orchestration
- **Cloud Build**: Automated CI/CD and deployment pipeline
- **PySpark**: Distributed processing engine
- **TensorFlow**: TFRecord format support

## Project Structure

```
chest_xray/
├── dags/                          # Airflow DAGs
│   └── image_processing_pipeline.py
├── scripts/
│   ├── dataproc_job.py           # Main PySpark processing script
│   └── test_image_processing_local.py  # Local testing script
├── config/
│   ├── pipeline_config.yaml      # Pipeline configuration
│   └── gcp_config.yaml           # GCP credentials/config template
├── .gcloudignore                  # Files excluded from Cloud Build
├── cloudbuild.yaml                # Cloud Build deployment configuration
├── requirements.txt              # Python dependencies
└── README.md                      # This file
```

## Prerequisites

1. **Google Cloud Platform Account**
   - Active GCP project with billing enabled
   - Required APIs enabled:
     - Cloud Storage API
     - Dataproc API
     - Cloud Composer API
     - Cloud Build API
     - Cloud Resource Manager API
2. **Local Environment**
   - Python 3.8+
   - Google Cloud SDK (`gcloud`)
   - Git

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure GCP

1. **Set up GCP Project**:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   gcloud auth application-default login
   ```

2. **Create GCS Buckets**:
   ```bash
   # Raw data bucket
   gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-chest-xray-raw
   
   # Processed data bucket
   gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-chest-xray-processed
   
   # Enable versioning on buckets (recommended for data versioning)
   gsutil versioning set on gs://YOUR_PROJECT_ID-chest-xray-raw
   gsutil versioning set on gs://YOUR_PROJECT_ID-chest-xray-processed
   ```

3. **Update Configuration Files**:
   - Edit `config/gcp_config.yaml` with your project details
   - Edit `config/pipeline_config.yaml` to adjust processing parameters

### 3. Upload Raw Data to GCS

```bash
# Upload images to GCS into respective folders raw/v1.0/train, raw/v1.0/val raw/v1.0/test  bucket folders
```

### 4. Set Up Composer (Airflow)

1. **Create Composer Environment** (via Console or CLI):
   ```bash
   gcloud composer environments create chest-xray-composer \
     --location us-central1 \
     --python-version 3 \
     --image-version composer-2.0.0-airflow-2.5.0
   ```

2. **Upload DAG to Composer**:
   ```bash
   # Get DAG folder path
   gcloud composer environments describe chest-xray-composer \
     --location us-central1 \
     --format="value(config.dagGcsPrefix)"
   
   # Copy DAG file
   gsutil cp dags/image_processing_pipeline.py gs://BUCKET/dags/
   ```

3. **Set Airflow Variables**:
   - In Airflow UI, go to Admin → Variables
   - Add the following variables:
     - `gcp_project_id`: Your GCP project ID
     - `raw_bucket`: `gs://YOUR_PROJECT_ID-chest-xray-raw`
     - `processed_bucket`: `gs://YOUR_PROJECT_ID-chest-xray-processed`
     - `dataproc_cluster_name`: `chest-xray-processing-cluster`
     - `gcp_region`: `us-central1`
     - `version_tag`: `v1.0`

### 5. Upload Processing Scripts to GCS

```bash
# Upload processing script and config
gsutil cp scripts/dataproc_job.py gs://YOUR_PROJECT_ID-chest-xray-processed/scripts/
gsutil cp config/pipeline_config.yaml gs://YOUR_PROJECT_ID-chest-xray-processed/config/
```

### 6. Automated Deployment with Cloud Build

The project includes Cloud Build configurations for automated deployment. This automates the deployment of DAGs, scripts, and Airflow variables.

Create a Cloud Build trigger that automatically deploys on git push:


#### What Gets Deployed

The Cloud Build process automatically:

1. **Deploys DAGs**: Uploads `dags/image_processing_pipeline.py` to Composer
2. **Uploads Scripts**: Copies processing scripts to GCS (`scripts/` and `config/`)
3. **Sets Airflow Variables**: Configures all required Airflow variables
4. **Validates Deployment**: Verifies that all components are deployed correctly

#### Cloud Build Configuration

The deployment uses the following files:

- **`cloudbuild.yaml`**: Main Cloud Build configuration
- **`.gcloudignore`**: Excludes unnecessary files from build context



#### Monitoring Deployments

- **Cloud Build Console**: https://console.cloud.google.com/cloud-build/builds
- **Build Logs**: Available in Cloud Logging
- **Composer UI**: Verify DAG appears in Airflow UI after deployment

## Usage

### Running the Pipeline

1. Open Airflow UI (URL provided by Composer)
2. Find `chest_xray_image_processing_pipeline` DAG
3. Enable the DAG
4. Trigger manually or wait for scheduled run


### Data Versioning with GCS

The pipeline uses a folder-based versioning strategy where bucket folders contain version numbers (e.g., `v1.0`, `v1.1`, `v2.0`) to create different versions of processed output. This approach provides:

- **Versioned Output**: Each processing run can output to a different version folder (e.g., `processed/v1.0/`, `processed/v1.1/`)
- **Version Tags**: Use semantic versioning in folder names to track different data versions
- **GCS Object Versioning**: Additionally, GCS object versioning is automatically enabled on your buckets, keeping previous file versions
- **Version Management**: Access different data versions by referencing the version folder path
- **Lifecycle Policies**: Configure automatic deletion of old versions to manage costs

#### Creating New Output Versions

To create a new version of processed output, specify a different version tag in the Airflow variable `version_tag`:

```bash
# Set a new version tag (e.g., v1.1)
gcloud composer environments run chest-xray-composer \
  --location us-central1 \
  variables -- \
  set version_tag "v1.1"
```

The pipeline will automatically:
- Read raw data from: `gs://BUCKET/raw/v1.1/`
- Write processed output to: `gs://BUCKET/processed/v1.1/`
- Create separate folders for each version, allowing you to maintain multiple data versions simultaneously

#### Accessing Different Data Versions

```bash
# List all version folders
gsutil ls gs://YOUR_PROJECT_ID-chest-xray-processed/processed/

# Access specific version outputs
gsutil ls gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0/
gsutil ls gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.1/
```


### Accessing Processed Data

#### TFRecord Format (TensorFlow)

```python
import tensorflow as tf

# Read TFRecord files
dataset = tf.data.TFRecordDataset(
    filenames=["gs://bucket/processed/v1.0/tfrecords/train/*.tfrecord"]
)

def parse_tfrecord(example_proto):
    feature_description = {
        'image': tf.io.FixedLenFeature([], tf.string),
        'label': tf.io.FixedLenFeature([], tf.int64),
        'image_shape': tf.io.FixedLenFeature([3], tf.int64),
    }
    parsed = tf.io.parse_single_example(example_proto, feature_description)
    image = tf.io.decode_raw(parsed['image'], tf.float32)
    image = tf.reshape(image, parsed['image_shape'])
    return image, parsed['label']

dataset = dataset.map(parse_tfrecord)
```

#### Parquet Format (PyTorch/Pandas)

```python
import pandas as pd
from pyspark.sql import SparkSession

# Using Spark
spark = SparkSession.builder.appName("ReadProcessedData").getOrCreate()
df = spark.read.parquet("gs://bucket/processed/v1.0/parquet/train")

# Convert to Pandas (for smaller datasets)
pandas_df = df.toPandas()
```

## Configuration

### Pipeline Configuration (`config/pipeline_config.yaml`)

Key parameters:

- **Image Processing**: Target dimensions, color space, normalization method
- **Augmentation**: Rotation, flipping, brightness adjustments
- **Denoising**: Optional noise reduction
- **Output Formats**: TFRecord and/or Parquet
- **Versioning**: Version tags and metadata tracking

### GCP Configuration (`config/gcp_config.yaml`)

Configure:
- GCP project ID and region
- GCS bucket names
- Dataproc cluster settings
- Service account credentials

## Processing Steps

The pipeline implements the following transformation steps:

1. **Image Acquisition**: Read images from GCS
2. **Resizing**: Resize to target dimensions (224x224)
3. **Normalization**: Min-max or z-score scaling
4. **Color Space Conversion**: RGB to grayscale (if needed)
5. **Data Augmentation**: Rotation, flip, brightness (configurable)
6. **Denoising**: Gaussian blur or median filter (optional)
7. **Feature Extraction**: Histogram features (optional, for classical ML)
8. **Flattening**: Reshape for ML models
9. **Label Encoding**: Binary encoding (NORMAL=0, PNEUMONIA=1)
10. **Batch Creation**: Create batches of configurable size
11. **Format Export**: TFRecord (TensorFlow) and Parquet (PyTorch)
12. **Versioning**: GCS object versioning for data version management

## Monitoring and Troubleshooting

### Check Pipeline Status

- **Airflow**: Monitor DAG runs in Airflow UI
- **Dataproc**: Check job status in GCP Console
- **GCS**: Verify output files in processed bucket


## Cost Optimization

1. **Auto-delete Clusters**: Dataproc clusters are deleted after job completion
2. **Preemptible Workers**: Use preemptible VMs for cost savings
3. **Lifecycle Policies**: Set GCS lifecycle policies for old data
4. **Scheduled Runs**: Run pipeline on schedule rather than continuously


## Next Steps

1. **ML Training**: Use processed data for model training
2. **Experiment Tracking**: Integrate with MLflow or similar tools
3. **Monitoring**: Set up alerts for pipeline failures
4. **Scaling**: Adjust cluster size based on data volume

