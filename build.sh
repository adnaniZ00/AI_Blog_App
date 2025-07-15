#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies (FFmpeg)
echo "Installing system dependencies..."
apt-get update && apt-get install -y ffmpeg

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate