"""
Airflow DAG for Image Processing Pipeline
Orchestrates the complete data pipeline from GCS upload to processed data versioning.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import (
    DataprocSubmitJobOperator,
    DataprocStartClusterOperator,
    DataprocStopClusterOperator,
)
from airflow.providers.google.cloud.operators.gcs import (
    GCSListObjectsOperator,
)

from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import yaml
import json
from google.cloud import storage


# Default arguments
default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

# DAG configuration
dag_id = 'chest_xray_image_processing_pipeline'
schedule_interval = '@weekly'  # Run weekly, adjust as needed

# Load configuration (can be stored in Airflow Variables or GCS)


def load_config():
    """Load configuration from Airflow Variables or default."""
    try:
        # Try to load from pipeline_config variable (JSON string)
        config_str = Variable.get("pipeline_config", default_var=None)
        if config_str and config_str != "{}":
            return json.loads(config_str)
    except Exception as e:
        print(f"Could not load pipeline_config variable: {e}")

    # Fallback: Load from individual Airflow Variables
    try:
        config = {
            "gcp": {
                "project_id": Variable.get("gcp_project_id", default_var=""),
                "region": Variable.get("gcp_region", default_var="us-central1")
            },
            "gcs": {
                "raw_bucket": Variable.get("raw_bucket", default_var=""),
                "processed_bucket": Variable.get("processed_bucket", default_var="")
            },
            "dataproc": {
                "cluster_name": Variable.get("dataproc_cluster_name", default_var="chest-xray-processing-cluster"),
                "num_workers": int(Variable.get("dataproc_num_workers", default_var="2")),
                "master_machine_type": Variable.get("dataproc_master_machine_type", default_var="n1-standard-4"),
                "worker_machine_type": Variable.get("dataproc_worker_machine_type", default_var="n1-standard-4")
            },
            "versioning": {
                "version_tag": Variable.get("version_tag", default_var="v1.0")
            }
        }
        return config
    except Exception as e:
        print(f"Error loading individual variables: {e}")
        # Ultimate fallback with empty values
        return {
            "gcp": {
                "project_id": "",
                "region": "us-central1"
            },
            "gcs": {
                "raw_bucket": "",
                "processed_bucket": ""
            },
            "dataproc": {
                "cluster_name": "chest-xray-processing-cluster",
                "num_workers": 2,
                "master_machine_type": "n1-standard-4",
                "worker_machine_type": "n1-standard-4"
            },
            "versioning": {
                "version_tag": "v1.0"
            }
        }


def validate_gcs_upload(**context):
    """Validate that raw images exist in GCS."""
    config = load_config()

    # 1. Get the raw_bucket path
    raw_bucket = config.get("gcs", {}).get("raw_bucket")

    # 2. Safety check: If config is missing or raw_bucket is empty
    if not raw_bucket:
        print(f"configg: {config}")
        raise ValueError(
            "Configuration error: 'raw_bucket' is empty or not found in config.yaml")

    version_tag = config.get("versioning", {}).get("version_tag", "v1.0")

    client = storage.Client()

    # 3. Robust parsing: handles 'gs://bucket-name', 'bucket-name', or 'gs://bucket-name/folder'
    bucket_name = raw_bucket.replace("gs://", "").strip("/").split("/")[0]

    if not bucket_name:
        raise ValueError(f"Could not parse bucket name from: {raw_bucket}")

    bucket = client.bucket(bucket_name)

    # 4. Check if files exist
    # Note: list_blobs is an iterator; using max_results prevents loading thousands of objects into memory
    blobs = list(bucket.list_blobs(
        prefix=f"raw/{version_tag}/", max_results=10))

    if len(blobs) == 0:
        raise ValueError(
            f"No images found in gs://{bucket_name}/raw/{version_tag}/. Please check your path.")

    print(f"Validation successful. Found files starting with: {blobs[0].name}")
    return True


def validate_processed_output(**context):
    """Validate that processed output exists in GCS."""
    config = load_config()
    processed_bucket = config.get("gcs", {}).get("processed_bucket", "")
    version_tag = config.get("versioning", {}).get("version_tag", "v1.0")
    print(f"processed_bucket: {processed_bucket}")
    print(f"configg: {config}")

    if not processed_bucket:
        raise ValueError(
            "Configuration error: 'processed_bucket' is empty or not found in config")

    client = storage.Client()

    # Construct the expected output path
    output_path = f"{processed_bucket}/processed/{version_tag}"

    # Parse bucket name and prefix
    # Handle both 'gs://bucket/path' and 'bucket/path' formats
    path_clean = output_path.replace("gs://", "").strip("/")
    parts = path_clean.split("/", 1)
    bucket_name = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    if not bucket_name:
        raise ValueError(f"Could not parse bucket name from: {output_path}")

    bucket = client.bucket(bucket_name)

    # Check for processed output files
    # Look for parquet files, metadata.json, or tfrecords
    print(f"Validating processed output in gs://{bucket_name}/{prefix}")

    # Check for metadata.json (always created by the pipeline)
    metadata_blob = bucket.blob(
        f"{prefix}/metadata.json" if prefix else "metadata.json")
    if metadata_blob.exists():
        print(f"✓ Found metadata.json")
        # Optionally validate metadata content
        try:
            metadata_content = metadata_blob.download_as_text()
            metadata = json.loads(metadata_content)
            processed_count = metadata.get("processed_images", 0)
            print(f"✓ Processed images count: {processed_count}")
        except Exception as e:
            print(f"Warning: Could not parse metadata.json: {e}")

    # Check for parquet files
    parquet_prefix = f"{prefix}/parquet" if prefix else "parquet"
    parquet_blobs = list(bucket.list_blobs(
        prefix=parquet_prefix, max_results=5))
    if len(parquet_blobs) > 0:
        print(f"✓ Found {len(parquet_blobs)} parquet file(s)")
    else:
        print(f"⚠ No parquet files found in {parquet_prefix}")

    # Check for tfrecord files (if enabled)
    tfrecord_prefix = f"{prefix}/tfrecords" if prefix else "tfrecords"
    tfrecord_blobs = list(bucket.list_blobs(
        prefix=tfrecord_prefix, max_results=5))
    if len(tfrecord_blobs) > 0:
        print(f"✓ Found {len(tfrecord_blobs)} tfrecord file(s)")

    # At minimum, we should have metadata.json or some output files
    all_blobs = list(bucket.list_blobs(prefix=prefix, max_results=10))
    if len(all_blobs) == 0:
        raise ValueError(
            f"No processed output found in gs://{bucket_name}/{prefix}. "
            "The Dataproc job may have failed or produced no output.")

    print(
        f"✓ Validation successful. Found processed output in gs://{bucket_name}/{prefix}")
    return True


def prepare_dataproc_job(**context):
    """Prepare Dataproc job configuration."""
    config = load_config()
    raw_bucket = config.get("gcs", {}).get("raw_bucket", "")
    processed_bucket = config.get("gcs", {}).get("processed_bucket", "")
    version_tag = config.get("versioning", {}).get("version_tag", "v1.0")
    project_id = config.get("gcp", {}).get("project_id", "")

    # GCS paths
    raw_gcs_path = f"{raw_bucket}/raw/{version_tag}"
    output_gcs_path = f"{processed_bucket}/processed/{version_tag}"
    config_gcs_path = f"{processed_bucket}/config/pipeline_config.yaml"
    script_gcs_path = f"{processed_bucket}/scripts/dataproc_job.py"

    # PySpark job configuration
    pyspark_job = {
        "main_python_file_uri": script_gcs_path,
        "args": [
            "--raw-gcs-path", raw_gcs_path,
            "--output-gcs-path", output_gcs_path,
            "--config-gcs-path", config_gcs_path
        ],
        "properties": {
            "spark.executor.memory": "4g",
            "spark.executor.cores": "2",
            "spark.driver.memory": "2g",
            "spark.sql.shuffle.partitions": "200",
            "spark.sql.adaptive.enabled": "true"
        }
    }

    job_config = {
        "reference": {
            "project_id": project_id
        },
        "placement": {
            "cluster_name": config.get("dataproc", {}).get("cluster_name", "chest-xray-processing-cluster")
        },
        "pyspark_job": pyspark_job
    }

    return job_config


# Create DAG
with DAG(
    dag_id=dag_id,
    default_args=default_args,
    description='Chest X-ray Image Processing Pipeline with Data Versioning',
    schedule_interval=schedule_interval,
    catchup=False,
    tags=['image-processing', 'dataproc', 'gcs'],
) as dag:

    # Task 1: Validate GCS Upload
    validate_upload = PythonOperator(
        task_id='validate_gcs_upload',
        python_callable=validate_gcs_upload,
        provide_context=True,
    )

    # Task 2: Create/Verify GCS Buckets
    def setup_buckets_if_needed(**context):
        """Create buckets if they don't exist."""
        from google.cloud import storage

        # Get bucket names from Airflow Variables
        raw_bucket = Variable.get("raw_bucket", default_var="")
        processed_bucket = Variable.get("processed_bucket", default_var="")
        region = Variable.get("gcp_region", default_var="us-central1")

        raw_bucket_name = raw_bucket.replace(
            "gs://", "").split("/")[0] if raw_bucket else ""
        processed_bucket_name = processed_bucket.replace(
            "gs://", "").split("/")[0] if processed_bucket else ""

        client = storage.Client()

        # Create raw bucket if it doesn't exist
        if raw_bucket_name:
            try:
                bucket = client.bucket(raw_bucket_name)
                if not bucket.exists():
                    bucket.create(location=region)
                    print(f"Created bucket: {raw_bucket_name}")
                else:
                    print(f"Bucket already exists: {raw_bucket_name}")
            except Exception as e:
                print(f"Error with raw bucket {raw_bucket_name}: {e}")

        # Create processed bucket if it doesn't exist
        if processed_bucket_name:
            try:
                bucket = client.bucket(processed_bucket_name)
                if not bucket.exists():
                    bucket.create(location=region)
                    print(f"Created bucket: {processed_bucket_name}")
                else:
                    print(f"Bucket already exists: {processed_bucket_name}")
            except Exception as e:
                print(
                    f"Error with processed bucket {processed_bucket_name}: {e}")

    setup_buckets = PythonOperator(
        task_id='setup_buckets',
        python_callable=setup_buckets_if_needed,
        provide_context=True,
    )

    # Task 3: Upload Processing Scripts to GCS
    upload_scripts = BashOperator(
        task_id='upload_scripts_to_gcs',
        bash_command="""
        gsutil cp scripts/dataproc_job.py {{ var.value.get('processed_bucket', '') }}/scripts/dataproc_job.py
        gsutil cp config/pipeline_config.yaml {{ var.value.get('processed_bucket', '') }}/config/pipeline_config.yaml
        """,
    )

    # Task 4: Start Dataproc Cluster
    # Note: Cluster must be created before running this DAG
    start_cluster = DataprocStartClusterOperator(
        task_id='start_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        # Will start cluster if it's stopped, or do nothing if already running
    )

    # Task 5: Prepare Job Configuration
    prepare_job = PythonOperator(
        task_id='prepare_dataproc_job',
        python_callable=prepare_dataproc_job,
        provide_context=True,
    )

    # Task 6: Submit Dataproc Job
    submit_job = DataprocSubmitJobOperator(
        task_id='submit_image_processing_job',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        job={
            "reference": {
                "project_id": "{{ var.value.get('gcp_project_id', '') }}"
            },
            "placement": {
                "cluster_name": "{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}"
            },
            "pyspark_job": {
                "main_python_file_uri": "{{ var.value.get('processed_bucket', '') }}/scripts/dataproc_job.py",
                "args": [
                    "--raw-gcs-path", "{{ var.value.get('raw_bucket', '') }}/raw/{{ var.value.get('version_tag', 'v1.0') }}",
                    "--output-gcs-path", "{{ var.value.get('processed_bucket', '') }}/processed/{{ var.value.get('version_tag', 'v1.0') }}",
                    "--config-gcs-path", "{{ var.value.get('processed_bucket', '') }}/config/pipeline_config.yaml"
                ],
                "properties": {
                    "spark.executor.memory": "4g",
                    "spark.executor.cores": "2",
                    "spark.driver.memory": "2g",
                    "spark.sql.shuffle.partitions": "200"
                }
            }
        },
        asynchronous=False,
    )

    # Task 7: Validate Output
    validate_output = PythonOperator(
        task_id='validate_processed_output',
        python_callable=validate_processed_output,
        provide_context=True,
    )


    # Task 8: Stop Dataproc Cluster (to save costs, keep cluster for reuse)
    stop_cluster = DataprocStopClusterOperator(
        task_id='stop_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        trigger_rule='all_done',  # Stop even if previous tasks failed
    )


    # Define task dependencies
    # Pipeline flow:
    # 1. Validate GCS upload
    # 2. Setup/create GCS buckets
    # 3. Upload processing scripts to GCS
    # 4. Start cluster (assumes cluster exists - create manually first)
    # 5. Prepare job configuration
    # 6. Submit image processing job
    # 7. Validate processed output
    # 8. Stop cluster (to save costs, but keep it for reuse)

    validate_upload >> setup_buckets >> upload_scripts >> start_cluster
    prepare_job >> submit_job >> validate_output >> stop_cluster
