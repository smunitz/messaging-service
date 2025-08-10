#!/bin/bash

set -e

echo "Starting the application..."
echo "Environment: ${ENV:-development}"

FLASK_APP=app.py flask run --host=0.0.0.0 --port=8080 &

echo "Application started successfully!" 