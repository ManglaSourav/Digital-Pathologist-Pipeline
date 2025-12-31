#!/bin/bash
# Script to set Airflow Variables in Composer

# Set variables
export COMPOSER_ENV="chest-xray-composer"
export REGION="us-central1"
export PROJECT_ID="copper-bot-481117-d1"

echo "=========================================="
echo "Setting Airflow Variables"
echo "=========================================="
echo "Composer Environment: $COMPOSER_ENV"
echo "Region: $REGION"
echo ""

# Set each variable
echo "Setting gcp_project_id..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set gcp_project_id "$PROJECT_ID"

echo "Setting raw_bucket..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set raw_bucket "gs://${PROJECT_ID}-chest-xray-raw"

echo "Setting processed_bucket..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set processed_bucket "gs://${PROJECT_ID}-chest-xray-processed"

echo "Setting dataproc_cluster_name..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set dataproc_cluster_name "chest-xray-processing-cluster"

echo "Setting gcp_region..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set gcp_region "us-central1"

echo "Setting version_tag..."
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  set version_tag "v1.0"

echo ""
echo "=========================================="
echo "✓ Variables set successfully!"
echo "=========================================="
echo ""
echo "Verify variables:"
gcloud composer environments run $COMPOSER_ENV \
  --location $REGION \
  variables -- \
  list

