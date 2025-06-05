import os
import json
import hashlib
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import time

app = FastAPI()

# Environment variables
VECTOR_DB_HOST = os.environ.get('VECTOR_DB_HOST', 'localhost')
VECTOR_DB_PORT = os.environ.get('VECTOR_DB_PORT', '8000')
VECTOR_DB_URL = f"http://{VECTOR_DB_HOST}:{VECTOR_DB_PORT}"
MODEL_CONTEXT_PROTOCOL = os.environ.get('USE_MCP', 'false').lower() == 'true'

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

class ProcessDocumentsRequest(BaseModel):
    document_dir: str = "/app/data/documents"

class QueryRequest(BaseModel):
    query: str
    max_results: int = 5

class RAGResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

def chunk_document(text, chunk_size=1000, overlap=200):
    """Split document into chunks with overlap"""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length and end - start == chunk_size:
            # Find the last period within the last 100 chars to create cleaner chunks
            last_period = text.rfind('.', start + chunk_size - 100, start + chunk_size)
            if last_period != -1:
                end = last_period + 1
        
        chunks.append(text[start:end])
        start = end - overlap if end < text_length else text_length
    
    return chunks

@app.post("/process_documents")
async def process_documents(request: ProcessDocumentsRequest):
    document_dir = request.document_dir
    
    try:
        # Process all documents in the directory
        count = 0
        for filename in os.listdir(document_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(document_dir, filename)
                with open(file_path, 'r') as f:
                    doc_data = json.load(f)
                
                # Create chunks from the document
                chunks = chunk_document(doc_data['text'])
                
                # Process each chunk
                for i, chunk in enumerate(chunks):
                    # Create a unique ID for each chunk
                    doc_id = hashlib.md5(f"{doc_data['url']}_{i}".encode()).hexdigest()
                    
                    # Create metadata
                    metadata = {
                        "url": doc_data['url'],
                        "title": doc_data['title'],
                        "chunk_id": i,
                        "source": "Red Hat Documentation"
                    }
                    
                    # Add to vector database
                    response = requests.post(
                        f"{VECTOR_DB_URL}/add",
                        json={"documents": [{"id": doc_id, "text": chunk, "metadata": metadata}]}
                    )
                    
                    if response.status_code != 200:
                        raise HTTPException(status_code=500, detail=f"Failed to add document to vector DB: {response.text}")
                    
                    count += 1
        
        return {"status": "success", "processed_chunks": count}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=RAGResponse)
async def query(request: QueryRequest):
    try:
        # Query the vector database
        response = requests.post(
            f"{VECTOR_DB_URL}/query",
            json={"query_text": request.query, "n_results": request.max_results}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Vector DB query failed: {response.text}")
        
        results = response.json()
        
        # Prepare context from retrieved documents
        contexts = []
        sources = []
        
        for i in range(len(results['ids'][0])):
            doc_id = results['ids'][0][i]
            doc_text = results['documents'][0][i]
            metadata = results['metadatas'][0][i]
            
            contexts.append(doc_text)
            sources.append({
                "title": metadata.get("title", "Untitled"),
                "url": metadata.get("url", ""),
                "relevance_score": results['distances'][0][i] if 'distances' in results else None
            })
        
        # Combine contexts
        context = "\n\n".join(contexts)
        
        # If using Model Context Protocol server
        if MODEL_CONTEXT_PROTOCOL:
            # Replace with actual MCP server call
            answer = "This would use the Model Context Protocol server with the retrieved context"
        else:
            # Simple extractive QA using the retrieved context
            # In a real system, you would use an LLM here
            answer = f"Here are the most relevant sections from Red Hat documentation about '{request.query}':\n\n"
            answer += context[:500] + "..."  # Simplified for this example
            
        return {
            "answer": answer,
            "sources": sources
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
