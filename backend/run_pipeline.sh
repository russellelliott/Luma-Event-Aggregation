#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting Luma Event Aggregation Pipeline..."

echo "--------------------------------------------------"
echo "1. Fetching events..."
python3 fetchEvents.py

echo "--------------------------------------------------"
echo "2. Generating event descriptions..."
python3 generateEventDescriptions.py

echo "--------------------------------------------------"
echo "3. Classifying events..."
python3 classifyEvents.py

echo "--------------------------------------------------"
echo "✅ Pipeline completed successfully!"
