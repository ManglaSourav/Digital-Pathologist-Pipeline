#!/bin/bash
# Dataproc Initialization Script
# Installs required Python packages for image processing pipeline

set -e

echo "=========================================="
echo "Installing Python dependencies"
echo "=========================================="

# Update pip
pip install --upgrade pip

# Install image processing libraries
echo "Installing TensorFlow..."
pip install tensorflow==2.15.0

echo "Installing OpenCV..."
pip install opencv-python-headless==4.8.1.78

echo "Installing Pillow..."
pip install Pillow==10.1.0

echo "Installing PyYAML..."
pip install PyYAML==6.0.1

echo "Installing NumPy (if not already installed)..."
pip install numpy==1.24.3

echo "=========================================="
echo "✓ All dependencies installed successfully"
echo "=========================================="

# Verify installations
echo "Verifying installations..."
python3 -c "import tensorflow as tf; print(f'TensorFlow version: {tf.__version__}')"
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"
python3 -c "from PIL import Image; print('Pillow imported successfully')"
python3 -c "import yaml; print('PyYAML imported successfully')"
python3 -c "import numpy as np; print(f'NumPy version: {np.__version__}')"

echo "=========================================="
echo "✓ All packages verified"
echo "=========================================="

