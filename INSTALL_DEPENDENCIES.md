# Installing Dependencies

This guide helps you install the required Python dependencies for the project.

## Option 1: Using Virtual Environment (Recommended)

### Step 1: Create Virtual Environment

```bash
# Navigate to project directory
cd /Users/souravmangla/Desktop/chest_xray

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

### Step 3: Verify Installation

```bash
# Check if google-cloud-storage is installed
python -c "from google.cloud import storage; print('✓ google-cloud-storage installed')"

# Check if other key packages are installed
python -c "import yaml; print('✓ pyyaml installed')"
python -c "from tqdm import tqdm; print('✓ tqdm installed')"
```

### Step 4: Use the Scripts

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Now run your scripts
python scripts/upload_to_gcs.py --help
```

## Option 2: Quick Install (Minimal Dependencies)

If you only need to upload files to GCS:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install only what's needed for upload script
pip install google-cloud-storage pyyaml tqdm
```

## Option 3: Using Setup Script

We've provided a setup script for convenience:

```bash
# Make script executable
chmod +x setup_venv.sh

# Run setup script
./setup_venv.sh

# Activate virtual environment
source venv/bin/activate
```

## Troubleshooting

### Issue: "externally-managed-environment" Error

**Solution:** Use a virtual environment (Option 1 or 3 above)

### Issue: "No module named 'google.cloud'"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Install the package
pip install google-cloud-storage
```

### Issue: Permission Denied

**Solution:** Don't use `sudo`. Use a virtual environment instead.

### Issue: pip not found

**Solution:**
```bash
# Use python3 -m pip instead
python3 -m pip install google-cloud-storage
```

## Activating Virtual Environment

**Every time you want to use the scripts:**

```bash
cd /Users/souravmangla/Desktop/chest_xray
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt when it's active.

**To deactivate:**
```bash
deactivate
```

## Verifying Installation

Run this to verify all key dependencies:

```bash
python -c "
import sys
packages = [
    'google.cloud.storage',
    'yaml',
    'tqdm',
    'PIL',
    'cv2',
    'numpy'
]
missing = []
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✓ {pkg}')
    except ImportError:
        print(f'✗ {pkg} - MISSING')
        missing.append(pkg)

if missing:
    print(f'\nMissing packages: {missing}')
    print('Install with: pip install -r requirements.txt')
    sys.exit(1)
else:
    print('\nAll dependencies installed!')
"
```

