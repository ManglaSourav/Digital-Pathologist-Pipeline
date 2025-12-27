# Install google-cloud-storage - Step by Step

## Environment Summary

- **Python:** 3.14.2 (Homebrew)
- **Location:** `/usr/local/opt/python@3.14/bin/python3.14`
- **Pip:** `/usr/local/bin/pip3`
- **Status:** Externally managed (requires venv or --break-system-packages)

## ✅ SOLUTION: Create Virtual Environment (Recommended)

**Run these commands in your terminal:**

```bash
# 1. Navigate to project
cd /Users/souravmangla/Desktop/chest_xray

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate it
source venv/bin/activate

# 4. Upgrade pip
pip install --upgrade pip

# 5. Install packages
pip install google-cloud-storage pyyaml tqdm

# 6. Verify installation
python -c "from google.cloud import storage; print('✓ SUCCESS!')"
```

**After installation, always activate venv before running scripts:**
```bash
source venv/bin/activate
python scripts/upload_to_gcs.py --help
```

---

## Alternative: Install with --break-system-packages (Not Recommended)

If you can't create a venv, you can override the protection:

```bash
python3 -m pip install --user --break-system-packages google-cloud-storage pyyaml tqdm
```

⚠️ **Warning:** This modifies your system Python. Use virtual environment instead.

---

## Alternative: Use Conda

If you prefer conda:

```bash
# Create conda environment
conda create -n chest_xray python=3.14 -y

# Activate it
conda activate chest_xray

# Install packages
pip install google-cloud-storage pyyaml tqdm

# Verify
python -c "from google.cloud import storage; print('✓ SUCCESS!')"
```

---

## Verify Installation Location

After installing, check where packages are installed:

```bash
# If using venv (activate first)
source venv/bin/activate
python -c "import google.cloud.storage; print(google.cloud.storage.__file__)"

# Should show something like:
# /Users/souravmangla/Desktop/chest_xray/venv/lib/python3.14/site-packages/google/cloud/storage/__init__.py
```

---

## Troubleshooting

### "ModuleNotFoundError" after installation

1. **Make sure venv is activated:**
   ```bash
   source venv/bin/activate
   # You should see (venv) in your prompt
   ```

2. **Check which Python you're using:**
   ```bash
   which python
   # Should show: /Users/souravmangla/Desktop/chest_xray/venv/bin/python
   ```

3. **Restart your IDE/terminal** - Python may have cached import paths

### "Permission denied" when creating venv

Try:
```bash
python3 -m venv --without-pip venv
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python
pip install google-cloud-storage pyyaml tqdm
```

---

## Quick Reference

**Every time you want to use the scripts:**

```bash
cd /Users/souravmangla/Desktop/chest_xray
source venv/bin/activate  # ← Don't forget this!
python scripts/upload_to_gcs.py [your arguments]
```

**To deactivate venv:**
```bash
deactivate
```

