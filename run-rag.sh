#!/bin/bash

# Clean up first
./cleanup.sh

# Create network
podman network create rhel-doc-rag-network 2>/dev/null || true

echo "Building containers..."
podman build -t rhel-doc-rag_vector-db ./vector-db/
podman build -t rhel-doc-rag_llm-service ./llm-service/
podman build -t rhel-doc-rag_api-service ./api-service/
podman build -t rhel-doc-rag_data-processor ./data-processor/
podman build -t rhel-doc-rag_web-interface ./web-interface/

echo "Starting Qdrant..."
podman run -d --name vector-db --network rhel-doc-rag-network -p 6333:6333 docker.io/qdrant/qdrant:v1.4.1

echo "Waiting for Qdrant to start..."
sleep 5

echo "Starting LLM service..."
podman run -d --name llm-service --network rhel-doc-rag-network -p 8080:8080 -e MCP_SERVER_URL=http://localhost:8090 rhel-doc-rag_llm-service

echo "Processing documents..."
podman run --rm --name data-processor --network rhel-doc-rag-network -v $(pwd)/downloaded_docs:/data/documents -e VECTOR_DB_HOST=vector-db -e VECTOR_DB_PORT=6333 rhel-doc-rag_data-processor

echo "Starting API service..."
podman run -d --name api-service --network rhel-doc-rag-network -p 5000:5000 -e VECTOR_DB_HOST=vector-db -e VECTOR_DB_PORT=6333 -e LLM_SERVICE_HOST=llm-service -e LLM_SERVICE_PORT=8080 rhel-doc-rag_api-service

echo "Starting web interface..."
podman run -d --name web-interface --network rhel-doc-rag-network -p 80:80 rhel-doc-rag_web-interface

echo "RAG system is now running!"
echo "Web interface: http://localhost"
echo "API endpoint: http://localhost:5000"
echo "Qdrant dashboard: http://localhost:6333/dashboard"
