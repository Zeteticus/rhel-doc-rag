import os
import argparse
from pathlib import Path
import re
import html2text
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http import models
import magic
import pypdf

# Simple document loading functionality without dependencies
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
    # Initialize model and text splitter
    model = SentenceTransformer('all-MiniLM-L6-v2')
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    
    # Connect to Qdrant
    client = QdrantClient(host=vector_db_host, port=vector_db_port)
    
    # Create collection
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
                chunks = text_splitter.split_text(document_text)
                
                # Store in Qdrant
                for i, chunk in enumerate(chunks):
                    embedding = model.encode(chunk).tolist()
                    
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
