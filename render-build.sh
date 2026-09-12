#!/usr/bin/env bash
# exit on error
set -o errexit

# Update pip and install python requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install system dependencies needed for OpenCV on Render's Ubuntu environment

apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0
