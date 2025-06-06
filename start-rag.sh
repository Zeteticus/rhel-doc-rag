#!/bin/bash

# Create network if it doesn't exist
podman network create rhel-doc-rag-network 2>/dev/null || true

echo "Starting Qdrant vector database..."
podman run -d --name vector-db --network rhel-doc-rag-network -p 6333:6333 -v ./vector_data:/qdrant/storage docker.io/qdrant/qdrant:v1.4.1

echo "Waiting for Qdrant to be ready..."
while ! podman exec vector-db wget --quiet --spider http://localhost:6333/health; do
  echo "Waiting for Qdrant..."
  sleep 2
done

echo "Starting LLM service..."
podman run -d --name llm-service --network rhel-doc-rag-network -p 8080:8080 -e MCP_SERVER_URL=http://localhost:8090 rhel-doc-rag_llm-service

echo "Processing documents..."
podman run --rm --name data-processor --network rhel-doc-rag-network -v ./downloaded_docs:/data/documents -e VECTOR_DB_HOST=vector-db -e VECTOR_DB_PORT=6333 rhel-doc-rag_data-processor

echo "Starting API service..."
podman run -d --name api-service --network rhel-doc-rag-network -p 5000:5000 -e VECTOR_DB_HOST=vector-db -e VECTOR_DB_PORT=6333 -e LLM_SERVICE_HOST=llm-service -e LLM_SERVICE_PORT=8080 rhel-doc-rag_api-service

echo "Starting web interface..."
podman run -d --name web-interface --network rhel-doc-rag-network -p 80:80 rhel-doc-rag_web-interface

echo "RAG system is now running!"
echo "Web interface: http://localhost"
echo "API endpoint: http://localhost:5000"
echo "Qdrant dashboard: http://localhost:6333/dashboard"
