# Chest X-ray Image Processing Pipeline

A production-grade data pipeline for processing chest X-ray images with data versioning capabilities. This pipeline uses Google Cloud Platform services (GCS, Dataproc, Composer) to transform raw images into ML-ready formats (TFRecord and Parquet) with GCS versioning support.

## Architecture Overview

```
Raw Images (Local)
  ↓
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
- **Dataproc**: Serverless Spark cluster for distributed image processing
- **Composer (Airflow)**: Managed workflow orchestration
- **PySpark**: Distributed processing engine
- **TensorFlow**: TFRecord format support
- **PyArrow**: Parquet format support

## Project Structure

```
chest_xray/
├── dags/                          # Airflow DAGs
│   └── image_processing_pipeline.py
├── scripts/
│   ├── upload_to_gcs.py          # Initial data upload utility
│   └── dataproc_job.py           # Main PySpark processing script
├── config/
│   ├── pipeline_config.yaml      # Pipeline configuration
│   └── gcp_config.yaml           # GCP credentials/config template
├── .gcloudignore                  # Files excluded from Cloud Build
├── cloudbuild.yaml                # Cloud Build deployment configuration
├── set_airflow_variables.sh       # Manual Airflow variables setup
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
     - Cloud Resource Manager API

2. **Service Account**
   - Service account with following roles:
     - Storage Admin
     - Dataproc Worker
     - Composer Worker

3. **Local Environment**
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
# Upload images to GCS
python scripts/upload_to_gcs.py \
  --local-dir ./train \
  --gcs-bucket gs://YOUR_PROJECT_ID-chest-xray-raw \
  --gcs-prefix raw/v1.0/train \
  --extensions .jpeg .jpg

python scripts/upload_to_gcs.py \
  --local-dir ./val \
  --gcs-bucket gs://YOUR_PROJECT_ID-chest-xray-raw \
  --gcs-prefix raw/v1.0/val \
  --extensions .jpeg .jpg

python scripts/upload_to_gcs.py \
  --local-dir ./test \
  --gcs-bucket gs://YOUR_PROJECT_ID-chest-xray-raw \
  --gcs-prefix raw/v1.0/test \
  --extensions .jpeg .jpg
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

#### Option 1: Manual Cloud Build Trigger

```bash
# Trigger Cloud Build manually
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=YOUR_PROJECT_ID \
  --substitutions="_REGION=us-central1,_COMPOSER_ENV=chest-xray-composer,_VERSION_TAG=v1.0"
```

#### Option 2: Set Up Automated Triggers

Create a Cloud Build trigger that automatically deploys on git push:

```bash
# For GitHub repositories
gcloud builds triggers create github \
  --name="deploy-chest-xray-pipeline" \
  --repo-name=REPO_NAME \
  --repo-owner=REPO_OWNER \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --substitutions="_REGION=us-central1,_COMPOSER_ENV=chest-xray-composer" \
  --project=YOUR_PROJECT_ID

# For Cloud Source Repositories
gcloud builds triggers create cloud-source-repositories \
  --name="deploy-chest-xray-pipeline" \
  --repo=REPO_NAME \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --substitutions="_REGION=us-central1,_COMPOSER_ENV=chest-xray-composer" \
  --project=YOUR_PROJECT_ID
```

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

#### Required Permissions

The Cloud Build service account needs the following roles:

- `roles/composer.worker` - To deploy DAGs and set variables
- `roles/storage.admin` - To upload files to GCS
- `roles/cloudbuild.builds.editor` - To run Cloud Build jobs

Grant permissions:

```bash
PROJECT_ID=YOUR_PROJECT_ID
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/composer.worker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.admin"
```

#### Monitoring Deployments

- **Cloud Build Console**: https://console.cloud.google.com/cloud-build/builds
- **Build Logs**: Available in Cloud Logging
- **Composer UI**: Verify DAG appears in Airflow UI after deployment

## Usage

### Running the Pipeline

#### Option 1: Via Airflow UI

1. Open Airflow UI (URL provided by Composer)
2. Find `chest_xray_image_processing_pipeline` DAG
3. Enable the DAG
4. Trigger manually or wait for scheduled run

#### Option 2: Manual Dataproc Job

```bash
# Submit job directly to Dataproc
gcloud dataproc jobs submit pyspark \
  --cluster=chest-xray-processing-cluster \
  --region=us-central1 \
  --py-files=gs://YOUR_PROJECT_ID-chest-xray-processed/scripts/dataproc_job.py \
  -- \
  --raw-gcs-path=gs://YOUR_PROJECT_ID-chest-xray-raw/raw/v1.0 \
  --output-gcs-path=gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0 \
  --config-gcs-path=gs://YOUR_PROJECT_ID-chest-xray-processed/config/pipeline_config.yaml
```

### Data Versioning with GCS

GCS object versioning is automatically enabled on your buckets. This provides:

- **Automatic Versioning**: Every time a file is uploaded or updated, GCS keeps previous versions
- **Version Management**: Access previous versions using generation numbers
- **Lifecycle Policies**: Configure automatic deletion of old versions to manage costs

#### Accessing Previous Versions

```bash
# List all versions of a file
gsutil ls -a gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0/metadata.json

# Download a specific version
gsutil cp gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0/metadata.json#GENERATION_NUMBER ./metadata.json

# Restore a previous version
gsutil cp gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0/metadata.json#GENERATION_NUMBER \
  gs://YOUR_PROJECT_ID-chest-xray-processed/processed/v1.0/metadata.json
```

#### Managing Versions with Lifecycle Policies

```bash
# Create a lifecycle policy to delete old versions after 90 days
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 90,
          "isLive": false
        }
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://YOUR_PROJECT_ID-chest-xray-processed
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

### Common Issues

1. **Permission Errors**: Ensure service account has required roles
2. **Cluster Creation Failures**: Check quota limits and region availability
3. **Out of Memory**: Increase executor memory in Dataproc config
4. **Versioning Issues**: Verify GCS versioning is enabled on buckets

### Logs

- **Airflow Logs**: Available in Airflow UI task logs
- **Dataproc Logs**: Available in Cloud Logging
- **GCS**: Check metadata.json for processing statistics

## Cost Optimization

1. **Auto-delete Clusters**: Dataproc clusters are deleted after job completion
2. **Preemptible Workers**: Use preemptible VMs for cost savings
3. **Lifecycle Policies**: Set GCS lifecycle policies for old data
4. **Scheduled Runs**: Run pipeline on schedule rather than continuously

## Security Best Practices

1. **Service Accounts**: Use least-privilege service accounts
2. **Encryption**: Enable encryption at rest for GCS buckets
3. **IAM**: Restrict access to buckets and clusters
4. **Secrets**: Store credentials in Secret Manager (not in code)

## Versioning Strategy

- **Version Tags**: Use semantic versioning in folder structure (v1.0, v1.1, v2.0)
- **Metadata Tracking**: Store processing parameters and statistics in metadata.json
- **GCS Object Versioning**: Automatic versioning of all files uploaded to GCS
- **Experiment Comparison**: Compare different data versions by accessing different version tags
- **Rollback**: Easily revert to previous versions using GCS generation numbers

## Next Steps

1. **ML Training**: Use processed data for model training
2. **Experiment Tracking**: Integrate with MLflow or similar tools
3. **Monitoring**: Set up alerts for pipeline failures
4. **Scaling**: Adjust cluster size based on data volume

## Support

For issues or questions:
1. Check logs in Airflow and Cloud Logging
2. Review configuration files
3. Verify GCP permissions and quotas
4. Consult GCP documentation for service-specific issues

## License

[Add your license here]




<!-- 
this worked
/opt/conda/default/bin/pip install \
  numpy==1.21.6 \
  scipy==1.7.3 \
  tensorflow==2.10.1 
  
  1. Find the Python Path - on master node
  env | grep -E "PYSPARK_PYTHON|PYSPARK_DRIVER_PYTHON"
  my output: PYSPARK_PYTHON=/opt/conda/default/bin/python


# 1. Define the path
export CONDA_PY=/opt/conda/default/bin/python

# 2. Force install NumPy 1.23.5 (The most stable version for TF 2.13 on Python 3.8)
sudo $CONDA_PY -m pip install --no-cache-dir --force-reinstall numpy==1.23.5

# 3. Install TensorFlow 2.13.1 and the rest of your stack
sudo $CONDA_PY -m pip install --no-cache-dir \
    tensorflow==2.13.1 \
    opencv-python-headless==4.8.0.74 \
    Pillow==9.5.0 \
    PyYAML==6.0.1


  2. 
  
  -->