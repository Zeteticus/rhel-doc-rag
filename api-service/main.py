from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import hashlib
import numpy as np
from qdrant_client import QdrantClient

app = FastAPI(title="Red Hat Documentation RAG API")

# Configuration
VECTOR_DB_HOST = os.environ.get("VECTOR_DB_HOST", "localhost")
VECTOR_DB_PORT = int(os.environ.get("VECTOR_DB_PORT", "6333"))
LLM_SERVICE_HOST = os.environ.get("LLM_SERVICE_HOST", "localhost")
LLM_SERVICE_PORT = int(os.environ.get("LLM_SERVICE_PORT", "8080"))

# Connect to Qdrant
client = QdrantClient(host=VECTOR_DB_HOST, port=VECTOR_DB_PORT)

# Simple embedding function that doesn't require PyTorch
def simple_embedding(text, dimension=384):
    """Generate a simple deterministic embedding from text (not for production use)"""
    # Hash the text to get a deterministic seed
    text_hash = hashlib.md5(text.encode()).digest()
    np.random.seed(int.from_bytes(text_hash[:4], byteorder='little'))
    
    # Generate a random vector (this is NOT a good embedding, just for testing)
    embedding = np.random.randn(dimension)
    # Normalize to unit length
    return embedding / np.linalg.norm(embedding)

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    temperature: float = 0.7
    max_tokens: int = 512

@app.post("/query")
async def query_rag(request: QueryRequest):
    # Embed query
    query_embedding = simple_embedding(request.query).tolist()
    
    # Query vector database
    search_results = client.search(
        collection_name="redhat_docs",
        query_vector=query_embedding,
        limit=request.top_k
    )
    
    # Extract context documents and metadata
    context_docs = []
    sources = []
    
    for hit in search_results:
        text = hit.payload.get("text", "")
        context_docs.append(text)
        sources.append({
            "text": text,
            "source": hit.payload.get("source", ""),
            "title": hit.payload.get("title", ""),
            "score": hit.score
        })
    
    # Generate answer using LLM service
    async with httpx.AsyncClient() as client:
        llm_response = await client.post(
            f"http://{LLM_SERVICE_HOST}:{LLM_SERVICE_PORT}/generate",
            json={
                "prompt": request.query,
                "context": context_docs,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature
            }
        )
        
        if llm_response.status_code != 200:
            raise HTTPException(status_code=500, detail="LLM service error")
        
        answer = llm_response.json()["answer"]
    
    # Return answer and source documents
    return {
        "answer": answer,
        "sources": sources
    }

# Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
