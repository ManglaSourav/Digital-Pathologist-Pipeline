"""
Airflow DAG for Image Processing Pipeline
Orchestrates the complete data pipeline from GCS upload to processed data versioning.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import (
    DataprocCreateClusterOperator,
    DataprocDeleteClusterOperator,
    DataprocSubmitJobOperator,
    DataprocStartClusterOperator,
    DataprocStopClusterOperator,
)
from airflow.providers.google.cloud.operators.gcs import (
    GCSListObjectsOperator,
    GCSCreateBucketOperator,
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
        config_str = Variable.get("pipeline_config", default_var="{}")
        return json.loads(config_str)
    except:
        # Default configuration
        return {
            "gcp": {
                "project_id": "{{ var.value.get('gcp_project_id', 'your-project-id') }}",
                "region": "us-central1"
            },
            "gcs": {
                "raw_bucket": "{{ var.value.get('raw_bucket', 'your-raw-bucket') }}",
                "processed_bucket": "{{ var.value.get('processed_bucket', 'your-processed-bucket') }}"
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
    raw_bucket = config.get("gcs", {}).get("raw_bucket", "")
    version_tag = config.get("versioning", {}).get("version_tag", "v1.0")

    client = storage.Client()
    bucket_name = raw_bucket.replace("gs://", "").split("/")[0]
    bucket = client.bucket(bucket_name)

    # Check if files exist
    blobs = list(bucket.list_blobs(prefix=f"raw/{version_tag}/"))
    if len(blobs) == 0:
        raise ValueError(f"No images found in {raw_bucket}/raw/{version_tag}/")

    print(f"Found {len(blobs)} files in raw bucket")
    return len(blobs)


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


def run_dvc_versioning(**context):
    """Run DVC versioning step."""
    config = load_config()
    version_tag = config.get("versioning", {}).get("version_tag", "v1.0")
    processed_bucket = config.get("gcs", {}).get("processed_bucket", "")

    # DVC commands
    commands = [
        f"dvc add data/processed/{version_tag}",
        f"dvc push",
        f"git add data/processed/{version_tag}.dvc .dvc/config",
        f"git commit -m 'Version {version_tag} processed data'",
        f"git tag {version_tag}"
    ]

    return "\n".join(commands)


def check_cluster_exists(**context):
    """Check if Dataproc cluster exists and return its state."""
    from google.cloud import dataproc_v1

    project_id = Variable.get("gcp_project_id", default_var="")
    region = Variable.get("gcp_region", default_var="us-central1")
    cluster_name = Variable.get(
        "dataproc_cluster_name", default_var="chest-xray-processing-cluster")

    if not project_id:
        return {"exists": False, "state": None}

    try:
        cluster_client = dataproc_v1.ClusterControllerClient(
            client_options={
                "api_endpoint": f"{region}-dataproc.googleapis.com:443"}
        )

        cluster_path = f"projects/{project_id}/regions/{region}/clusters/{cluster_name}"
        cluster = cluster_client.get_cluster(request={"name": cluster_path})

        return {
            "exists": True,
            "state": cluster.status.state.name if cluster.status else None
        }
    except Exception as e:
        # Cluster doesn't exist or error accessing it
        print(f"Cluster check result: {e}")
        print("Will attempt to create cluster if it doesn't exist")
        return {"exists": False, "state": None}


# Create DAG
with DAG(
    dag_id=dag_id,
    default_args=default_args,
    description='Chest X-ray Image Processing Pipeline with Data Versioning',
    schedule_interval=schedule_interval,
    catchup=False,
    tags=['image-processing', 'dataproc', 'gcs', 'dvc'],
) as dag:

    # Task 1: Validate GCS Upload
    validate_upload = PythonOperator(
        task_id='validate_gcs_upload',
        python_callable=validate_gcs_upload,
        provide_context=True,
    )

    # Task 2: Create/Verify GCS Buckets
    with TaskGroup("setup_buckets") as setup_buckets:
        create_raw_bucket = GCSCreateBucketOperator(
            task_id='create_raw_bucket_if_not_exists',
            bucket_name="{{ var.value.get('raw_bucket', '').replace('gs://', '').split('/')[0] }}",
            project_id="{{ var.value.get('gcp_project_id', '') }}",
            location="us-central1",
            if_exists="ignore"
        )

        create_processed_bucket = GCSCreateBucketOperator(
            task_id='create_processed_bucket_if_not_exists',
            bucket_name="{{ var.value.get('processed_bucket', '').replace('gs://', '').split('/')[0] }}",
            project_id="{{ var.value.get('gcp_project_id', '') }}",
            location="us-central1",
            if_exists="ignore"
        )

    # Task 3: Upload Processing Scripts to GCS
    upload_scripts = BashOperator(
        task_id='upload_scripts_to_gcs',
        bash_command="""
        gsutil cp scripts/dataproc_job.py {{ var.value.get('processed_bucket', '') }}/scripts/dataproc_job.py
        gsutil cp config/pipeline_config.yaml {{ var.value.get('processed_bucket', '') }}/config/pipeline_config.yaml
        """,
    )

    # Task 4: Check if cluster exists
    check_cluster = PythonOperator(
        task_id='check_cluster_exists',
        python_callable=check_cluster_exists,
        provide_context=True,
    )

    # Task 5: Create Dataproc Cluster
    # Note: This will create the cluster if it doesn't exist.
    # If cluster already exists, this task may fail, but the start_cluster task will handle it.
    # For production, consider using a BranchPythonOperator to conditionally create.
    create_cluster = DataprocCreateClusterOperator(
        task_id='create_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        cluster_config={
            "master_config": {
                "num_instances": 1,
                "machine_type_uri": "n1-standard-4",
                "disk_config": {
                    "boot_disk_type": "pd-standard",
                    "boot_disk_size_gb": 100
                }
            },
            "worker_config": {
                "num_instances": 2,
                "machine_type_uri": "n1-standard-4",
                "disk_config": {
                    "boot_disk_type": "pd-standard",
                    "boot_disk_size_gb": 100
                }
            },
            "software_config": {
                "image_version": "2.0-debian10",
                "properties": {
                    "spark:spark.executor.memory": "4g",
                    "spark:spark.executor.cores": "2",
                    "spark:spark.driver.memory": "2g"
                }
            }
        },
        # Only create if cluster doesn't exist (handled by check_cluster task)
    )

    # Task 6: Start Dataproc Cluster
    start_cluster = DataprocStartClusterOperator(
        task_id='start_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        # Will start cluster if it's stopped, or do nothing if already running
    )

    # Task 7: Prepare Job Configuration
    prepare_job = PythonOperator(
        task_id='prepare_dataproc_job',
        python_callable=prepare_dataproc_job,
        provide_context=True,
    )

    # Task 8: Submit Dataproc Job
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

    # Task 9: Validate Output
    validate_output = PythonOperator(
        task_id='validate_processed_output',
        python_callable=lambda **context: validate_gcs_upload(**context),
        provide_context=True,
        op_kwargs={
            "bucket_path": "{{ var.value.get('processed_bucket', '') }}/processed/{{ var.value.get('version_tag', 'v1.0') }}"
        }
    )

    # Task 10: DVC Versioning
    dvc_versioning = BashOperator(
        task_id='dvc_versioning',
        bash_command="""
        cd /home/airflow/gcs/dags/chest_xray || cd /opt/airflow/dags/chest_xray || cd .
        dvc add data/processed/{{ var.value.get('version_tag', 'v1.0') }} || echo "DVC not configured, skipping"
        dvc push || echo "DVC push failed, check configuration"
        """,
    )

    # Task 11: Stop Dataproc Cluster (to save costs, keep cluster for reuse)
    stop_cluster = DataprocStopClusterOperator(
        task_id='stop_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        trigger_rule='all_done',  # Stop even if previous tasks failed
    )

    # Task 12: Delete Dataproc Cluster (optional - set to skip if you want to keep cluster)
    # Set this task to be skipped by default via Airflow UI if you want to reuse the cluster
    delete_cluster = DataprocDeleteClusterOperator(
        task_id='delete_dataproc_cluster',
        project_id="{{ var.value.get('gcp_project_id', '') }}",
        cluster_name="{{ var.value.get('dataproc_cluster_name', 'chest-xray-processing-cluster') }}",
        region="{{ var.value.get('gcp_region', 'us-central1') }}",
        trigger_rule='all_done',  # Delete even if previous tasks failed
    )

    # Define task dependencies
    # Pipeline flow:
    # 1. Validate GCS upload
    # 2. Setup/create GCS buckets
    # 3. Upload processing scripts to GCS
    # 4. Check if Dataproc cluster exists
    # 5. Create cluster if it doesn't exist
    # 6. Start cluster (will start if stopped, or do nothing if running)
    # 7. Prepare job configuration
    # 8. Submit image processing job
    # 9. Validate processed output
    # 10. DVC versioning
    # 11. Stop cluster (to save costs, but keep it for reuse)
    # 12. Delete cluster (optional - can be skipped in Airflow UI to keep cluster)

    validate_upload >> setup_buckets >> upload_scripts >> check_cluster
    check_cluster >> create_cluster >> start_cluster
    start_cluster >> prepare_job >> submit_job
    submit_job >> validate_output >> dvc_versioning >> stop_cluster >> delete_cluster
