# Fix Missing Dependencies - Run These Commands

## Step-by-Step Fix

**Open your terminal and run these commands one by one:**

### Step 1: Navigate to Project Directory
```bash
cd /Users/souravmangla/Desktop/chest_xray
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
```

If that fails with permission error, try:
```bash
python3 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python
```

### Step 3: Activate Virtual Environment
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### Step 4: Upgrade pip
```bash
pip install --upgrade pip
```

### Step 5: Install Required Packages
```bash
pip install google-cloud-storage pyyaml tqdm
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

### Step 6: Verify Installation
```bash
python -c "from google.cloud import storage; print('✓ Success! google-cloud-storage is installed')"
```

### Step 7: Test Your Script
```bash
python scripts/upload_to_gcs.py --help
```

## Alternative: Install Without Virtual Environment (Not Recommended)

If you really can't use a virtual environment, you can install with `--user` flag:

```bash
pip install --user google-cloud-storage pyyaml tqdm
```

But **virtual environment is strongly recommended** to avoid conflicts.

## Every Time You Use the Scripts

**Always activate the virtual environment first:**

```bash
cd /Users/souravmangla/Desktop/chest_xray
source venv/bin/activate
```

Then run your scripts:
```bash
python scripts/upload_to_gcs.py --local-dir ./train --gcs-bucket gs://your-bucket --gcs-prefix raw/v1.0/train
```

## Troubleshooting

### If `python3` doesn't work:
```bash
python -m venv venv
```

### If `pip` doesn't work:
```bash
python3 -m pip install google-cloud-storage
```

### If you get "command not found":
Make sure you're in the project directory:
```bash
pwd
# Should show: /Users/souravmangla/Desktop/chest_xray
```

## Quick One-Liner (After venv is created)

```bash
source venv/bin/activate && pip install google-cloud-storage pyyaml tqdm
```

