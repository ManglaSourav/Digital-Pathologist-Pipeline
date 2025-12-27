#!/bin/bash
# Installation script for google-cloud-storage and dependencies

set -e  # Exit on error

echo "=========================================="
echo "Installing google-cloud-storage"
echo "=========================================="
echo ""

# Check if venv exists
if [ -d "venv" ]; then
    echo "⚠ Virtual environment already exists"
    echo "Activating existing venv..."
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo ""
echo "Upgrading pip..."
pip install --upgrade pip

echo ""
echo "Installing packages..."
pip install google-cloud-storage pyyaml tqdm

echo ""
echo "Verifying installation..."
python -c "from google.cloud import storage; print('✓ google-cloud-storage installed successfully!')" || {
    echo "✗ Verification failed"
    exit 1
}

echo ""
echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "To use the scripts, always activate venv first:"
echo "  source venv/bin/activate"
echo ""
echo "Then run your scripts:"
echo "  python scripts/upload_to_gcs.py --help"
echo ""

