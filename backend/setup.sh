#!/bin/bash
# Setup script for Shrimply Smart Backend with MySQL

echo "Setting up Shrimply Smart Backend..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your settings before continuing."
    echo "Press Enter to continue after editing..."
    read
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Populate thresholds
echo "Populating default thresholds..."
python manage.py populate_thresholds

# Create superuser
echo "Creating Django superuser..."
python manage.py createsuperuser

echo "Setup complete! Run 'python manage.py runserver' to start the server."