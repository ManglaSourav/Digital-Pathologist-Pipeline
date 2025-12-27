#!/usr/bin/env python3
"""
Environment Check and Installation Script
Checks Python environment and installs google-cloud-storage in the correct location.
"""

import sys
import subprocess
import os
from pathlib import Path

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def run_command(cmd, check=True):
    """Run a command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=check
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout.strip(), e.stderr.strip(), e.returncode

def check_python_env():
    """Check Python environment details."""
    print_section("Python Environment Details")
    
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"\nPython search paths:")
    for i, path in enumerate(sys.path, 1):
        print(f"  {i}. {path}")
    
    # Check user site-packages
    try:
        import site
        user_site = site.getusersitepackages()
        print(f"\nUser site-packages: {user_site}")
        if os.path.exists(user_site):
            print(f"  ✓ Exists")
        else:
            print(f"  ✗ Does not exist (will be created on first --user install)")
    except:
        pass

def check_pip_location():
    """Check where pip installs packages."""
    print_section("Pip Installation Locations")
    
    stdout, stderr, code = run_command("which pip3", check=False)
    if code == 0:
        print(f"pip3 location: {stdout}")
    else:
        print("pip3 not found in PATH")
    
    stdout, stderr, code = run_command("pip3 --version", check=False)
    if code == 0:
        print(f"pip3 version: {stdout}")
    
    # Check where pip would install
    stdout, stderr, code = run_command("python3 -m pip show pip", check=False)
    if code == 0:
        for line in stdout.split('\n'):
            if 'Location:' in line:
                print(f"pip install location: {line.split('Location:')[1].strip()}")

def check_google_cloud():
    """Check if google-cloud-storage is installed."""
    print_section("Google Cloud Storage Check")
    
    try:
        from google.cloud import storage
        print("✓ google-cloud-storage IS installed")
        print(f"  Location: {storage.__file__}")
        return True
    except ImportError as e:
        print("✗ google-cloud-storage is NOT installed")
        print(f"  Error: {e}")
        return False

def check_venv():
    """Check for virtual environment."""
    print_section("Virtual Environment Check")
    
    # Check if we're in a venv
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✓ Currently in a virtual environment")
        print(f"  venv path: {sys.prefix}")
        return True
    else:
        print("✗ Not in a virtual environment")
        
        # Check if venv directory exists
        project_dir = Path(__file__).parent
        venv_dir = project_dir / "venv"
        if venv_dir.exists():
            print(f"  ⚠ venv directory exists at: {venv_dir}")
            print("  But it's not activated!")
            return "exists"
        else:
            print("  No venv directory found")
            return False

def install_google_cloud_storage(method="user"):
    """Install google-cloud-storage."""
    print_section(f"Installing google-cloud-storage (method: {method})")
    
    if method == "user":
        cmd = "python3 -m pip install --user google-cloud-storage pyyaml tqdm"
        print(f"Running: {cmd}")
    elif method == "venv":
        cmd = "pip install google-cloud-storage pyyaml tqdm"
        print(f"Running: {cmd}")
    else:
        print(f"Unknown method: {method}")
        return False
    
    stdout, stderr, code = run_command(cmd, check=False)
    
    if code == 0:
        print("✓ Installation successful!")
        print("\nOutput:")
        print(stdout)
        return True
    else:
        print("✗ Installation failed!")
        print("\nError output:")
        print(stderr)
        return False

def main():
    """Main function."""
    print("\n" + "="*60)
    print("  ENVIRONMENT DIAGNOSTIC AND INSTALLATION TOOL")
    print("="*60)
    
    # Check environment
    check_python_env()
    check_pip_location()
    venv_status = check_venv()
    google_installed = check_google_cloud()
    
    # Installation decision
    print_section("Installation Plan")
    
    if google_installed:
        print("✓ google-cloud-storage is already installed!")
        print("\nYou can use it directly. If you're getting import errors,")
        print("make sure you're using the same Python interpreter.")
        return 0
    
    if venv_status is True:
        print("You're in a virtual environment. Installing there...")
        success = install_google_cloud_storage(method="venv")
    elif venv_status == "exists":
        print("⚠ venv directory exists but not activated!")
        print("\nOptions:")
        print("  1. Activate venv first: source venv/bin/activate")
        print("  2. Install in user site-packages (recommended for now)")
        choice = input("\nInstall in user site-packages? (y/n): ").lower()
        if choice == 'y':
            success = install_google_cloud_storage(method="user")
        else:
            print("Please activate venv first: source venv/bin/activate")
            return 1
    else:
        print("Not in venv. Options:")
        print("  1. Install in user site-packages (recommended)")
        print("  2. Create and use virtual environment (best practice)")
        choice = input("\nInstall in user site-packages? (y/n): ").lower()
        if choice == 'y':
            success = install_google_cloud_storage(method="user")
        else:
            print("\nCreating virtual environment...")
            stdout, stderr, code = run_command("python3 -m venv venv", check=False)
            if code == 0:
                print("✓ Virtual environment created!")
                print("\nPlease run: source venv/bin/activate")
                print("Then run this script again or: pip install google-cloud-storage")
                return 0
            else:
                print("✗ Failed to create venv. Installing in user site-packages instead...")
                success = install_google_cloud_storage(method="user")
    
    # Verify installation
    if success:
        print_section("Verification")
        google_installed = check_google_cloud()
        if google_installed:
            print("\n✓ SUCCESS! google-cloud-storage is now installed and ready to use!")
            return 0
        else:
            print("\n⚠ Installation completed but import still fails.")
            print("You may need to restart your Python session or IDE.")
            return 1
    else:
        print("\n✗ Installation failed. Please check the error messages above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

