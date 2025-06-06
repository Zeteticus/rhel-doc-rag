#!/bin/bash

echo "Cleaning up existing containers..."
# Run cleanup script first
./cleanup.sh

# Create network if it doesn't exist
podman network create rhel-doc-rag-network 2>/dev/null || true

echo "Starting Qdrant vector database..."
# Use absolute paths for volumes
CURRENT_DIR=$(pwd)
podman run -d --name vector-db --network rhel-doc-rag-network -p 6333:6333 -v ${CURRENT_DIR}/vector_data:/qdrant/storage docker.io/qdrant/qdrant:v1.4.1

# Check if container is running
if ! podman ps | grep -q vector-db; then
  echo "ERROR: Qdrant container failed to start. Checking logs:"
  podman logs vector-db
  exit 1
fi

echo "Qdrant started successfully. Checking health..."
# Check health externally instead of using exec
max_attempts=30
attempt=0
while ! curl -s http://localhost:6333/health > /dev/null; do
  attempt=$((attempt+1))
  if [ $attempt -gt $max_attempts ]; then
    echo "Qdrant failed to become healthy after $max_attempts attempts."
    exit 1
  fi
  echo "Waiting for Qdrant... (attempt $attempt/$max_attempts)"
  sleep 2
done

echo "Qdrant is healthy! Starting other services..."
