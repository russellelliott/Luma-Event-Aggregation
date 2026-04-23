#!/bin/bash

# Run topic clustering only (without fetch/description steps).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting topic clustering..."
python3 cluster_topics.py
echo "Topic clustering completed successfully."
