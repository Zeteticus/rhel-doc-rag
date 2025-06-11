import os
import argparse
from pathlib import Path
import re
import html2text
from qdrant_client import QdrantClient
from qdrant_client.http import models
import magic
import pypdf
import hashlib
import numpy as np

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

# Simple text splitter implementation
def simple_text_splitter(text, chunk_size=1000, chunk_overlap=200):
    """Split text into chunks of approximately chunk_size characters with overlap."""
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        # Find a good place to end this chunk (preferably at paragraph or sentence end)
        end = min(start + chunk_size, text_len)
        
        # If we're not at the end of the text, try to find a paragraph break
        if end < text_len:
            # Look for paragraph break
            paragraph_break = text.rfind('\n\n', start, end)
            
            # If found and not too far back, use it
            if paragraph_break != -1 and paragraph_break > start + chunk_size // 2:
                end = paragraph_break + 2
            else:
                # Look for sentence break (period followed by space)
                sentence_break = text.rfind('. ', start, end)
                if sentence_break != -1 and sentence_break > start + chunk_size // 2:
                    end = sentence_break + 2
        
        # Add this chunk
        chunks.append(text[start:end])
        
        # Move to next chunk with overlap
        start = max(start, end - chunk_overlap)
    
    return chunks

# Simple document loading functionality
def load_document(file_path):
    """Load document content based on file type."""
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    
    print(f"Processing {file_path} with mime type: {file_type}")
    
    text = ""
    try:
        if "pdf" in file_type:
            # Using pypdf for PDF files
            with open(file_path, 'rb') as f:
                pdf_reader = pypdf.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        elif "html" in file_type:
            # Using html2text for HTML files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html = f.read()
                h = html2text.HTML2Text()
                h.ignore_links = False
                text = h.handle(html)
        elif "text" in file_type:
            # Simple text loader for text files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            print(f"Unsupported file type: {file_type} for {file_path}")
            return None
        
        # Clean up text: remove extra newlines and spaces
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def process_documents(docs_dir, vector_db_host, vector_db_port):
    print(f"Connecting to Qdrant at {vector_db_host}:{vector_db_port}")
    
    # Connect to Qdrant
    client = QdrantClient(host=vector_db_host, port=vector_db_port)
    
    # Create collection - note we're using dimension 384 to match the normal sentence transformer
    client.recreate_collection(
        collection_name="redhat_docs",
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )
    
    # Track statistics
    total_files = 0
    processed_files = 0
    total_chunks = 0
    
    # Process files
    for root, _, files in os.walk(docs_dir):
        for file in files:
            file_path = os.path.join(root, file)
            total_files += 1
            
            # Load and process document
            document_text = load_document(file_path)
            if document_text:
                # Split text into chunks
                chunks = simple_text_splitter(document_text)
                
                # Store in Qdrant
                for i, chunk in enumerate(chunks):
                    # Generate simple embedding (not a good one, but doesn't require PyTorch)
                    embedding = simple_embedding(chunk).tolist()
                    
                    client.upsert(
                        collection_name="redhat_docs",
                        points=[models.PointStruct(
                            id=f"{Path(file_path).stem}_{i}",
                            vector=embedding,
                            payload={"text": chunk, "source": file_path, "title": Path(file_path).name, "chunk": i}
                        )]
                    )
                
                total_chunks += len(chunks)
                processed_files += 1
                print(f"Processed: {file_path} - {len(chunks)} chunks")
            
    print(f"Processing complete: {processed_files}/{total_files} files, {total_chunks} total chunks")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process documents and store in vector database")
    parser.add_argument("--docs-dir", required=True, help="Directory with documents")
    parser.add_argument("--vector-db-host", default="localhost", help="Vector DB host")
    parser.add_argument("--vector-db-port", type=int, default=6333, help="Vector DB port")
    
    args = parser.parse_args()
    process_documents(args.docs_dir, args.vector_db_host, args.vector_db_port)
