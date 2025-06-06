#!/bin/bash

echo "Stopping containers..."
podman stop vector-db llm-service api-service web-interface 2>/dev/null || true

echo "Removing containers..."
podman rm vector-db llm-service api-service web-interface 2>/dev/null || true

echo "Removing network..."
podman network rm rhel-doc-rag-network 2>/dev/null || true

echo "Cleanup complete. You can now restart the system."
