import os
import chromadb
from chromadb.config import Settings
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Initialize ChromaDB
CHROMA_DB_DIR = os.environ.get('CHROMA_DB_DIR', '/app/data/chroma')
client = chromadb.PersistentClient(path=CHROMA_DB_DIR, settings=Settings(anonymized_telemetry=False))

# Create collection if it doesn't exist
try:
    collection = client.get_collection("redhat_docs")
except:
    collection = client.create_collection("redhat_docs")

class Document(BaseModel):
    id: str
    text: str
    metadata: dict

class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5

class AddDocumentsRequest(BaseModel):
    documents: List[Document]

@app.post("/add")
def add_documents(request: AddDocumentsRequest):
    ids = [doc.id for doc in request.documents]
    documents = [doc.text for doc in request.documents]
    metadatas = [doc.metadata for doc in request.documents]
    
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    return {"status": "success", "count": len(ids)}

@app.post("/query")
def query(request: QueryRequest):
    results = collection.query(
        query_texts=[request.query_text],
        n_results=request.n_results
    )
    return results

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
