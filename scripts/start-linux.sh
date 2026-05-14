#!/bin/bash
set -e
cd "$(dirname "$0")/.."
docker compose up -d --build
echo "Prelegal is running at http://localhost:8000"
