

import pysqlite3
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,  # For HTML
    UnstructuredMarkdownLoader, # For Markdown
    # Add more loaders as needed (e.g., CSVLoader, etc.)
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import ollama
import sentence_transformers
import os
import logging
import re  # For regular expressions
from bs4 import BeautifulSoup # For HTML parsing
import magic  # For detecting file types more accurately

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ConversationalRAG:
    def __init__(self, chroma_db_path="./chroma_db"):
        self.db = None
        self.embeddings = None
        self.conversation_history = []
        self.chroma_db_path = chroma_db_path  # Store the path
        self.embedding_model_name = "BAAI/bge-base-en-v1.5" # Default embedding model

    def initialize_system(self, directory_path='/home/dots-pa/docs-rag-main/docs'):
        """Initialize the RAG system by loading and processing documents."""
        try:
            self.embeddings = HuggingFaceEmbeddings(model_name=self.embedding_model_name)
            self.db = self._load_or_create_db(directory_path)
            return "System initialized! You can start asking questions about the documentation."
        except Exception as e:
            logging.error(f"Error initializing system: {e}", exc_info=True)
            return f"Error initializing system: {e}"

    def _load_or_create_db(self, directory_path):
        """Loads an existing Chroma DB or creates a new one if it doesn't exist."""
        try:
            if os.path.exists(self.chroma_db_path):
                logging.info(f"Loading existing Chroma DB from {self.chroma_db_path}")
                return Chroma(persist_directory=self.chroma_db_path, embedding_function=self.embeddings)
            else:
                logging.info(f"Creating new Chroma DB at {self.chroma_db_path}")
                docs = self._load_documents(directory_path)
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
                texts = text_splitter.split_documents(docs)
                db = Chroma.from_documents(documents=texts, embedding=self.embeddings, persist_directory=self.chroma_db_path)
                db.persist() # Persist the database to disk
                return db
        except Exception as e:
            logging.error(f"Error loading or creating Chroma DB: {e}", exc_info=True)
            raise  # Re-raise the exception to be handled by initialize_system


    def _load_documents(self, directory_path):
        """Loads documents from the specified directory, handling different file types."""
        documents = []
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path):
                    file_type = magic.from_file(file_path, mime=True) # Accurately detect file type
                    logging.info(f"Loading file: {filename} with type: {file_type}")

                    if 'application/pdf' in file_type:
                        loader = PyPDFLoader(file_path)
                    elif 'text/plain' in file_type or filename.endswith('.txt'):
                        loader = TextLoader(file_path)
                    elif 'text/markdown' in file_type or filename.endswith('.md'):
                        loader = UnstructuredMarkdownLoader(file_path)
                    elif 'text/html' in file_type or filename.endswith('.html'):
                        loader = UnstructuredHTMLLoader(file_path)
                    else:
                        logging.warning(f"Unsupported file type for {filename}: {file_type}. Skipping.")
                        continue  # Skip to the next file

                    documents.extend(loader.load())
            except Exception as e:
                logging.error(f"Error loading file {filename}: {e}", exc_info=True)
        return documents



    def query_system(self, user_input, k=4, model="llama3.2"):
        """Process a user query while maintaining conversation context."""
        if self.db is None:
            return "Error: System not initialized. Please run initialize_system() first."

        self.conversation_history.append({"role": "user", "content": user_input})

        try:
            results = self.db.similarity_search(user_input, k=k)
            relevant_text = "\n".join(doc.page_content for doc in results)

            # Construct a more informative prompt
            prompt = self._create_prompt(user_input, relevant_text)

            output = ollama.generate(model=model, prompt=prompt, stream=False) # Disable streaming for simplicity
            response = output['response']

            self.conversation_history.append({"role": "assistant", "content": response})
            return response

        except Exception as e:
            logging.error(f"Error processing query: {e}", exc_info=True)
            return f"An error occurred while processing your query: {e}"

    def _create_prompt(self, user_input, relevant_text):
        """Creates a prompt with more context and instructions."""
        conversation_context = "\n".join([
            f"{'Assistant: ' if msg['role'] == 'assistant' else 'Human: '}{msg['content']}"
            for msg in self.conversation_history[-4:]  # Include last 4 messages for context
        ])

        prompt = f"""You are a helpful system administration assistant. Use the provided documentation to answer the user's question as accurately and concisely as possible.

        Reference Documentation:
        {relevant_text}

        Previous Conversation:
        {conversation_context}

        User Question: {user_input}

        Instructions:
        1.  Answer the user's question based on the Reference Documentation.
        2.  If the answer is not found in the Reference Documentation, truthfully say that you cannot find the answer.
        3.  When providing code examples, format them correctly and include comments to explain what the code does.
        4.  If the user asks about a specific error message, try to find the cause of the error and suggest possible solutions.
        5. Be concise and to the point.
        """
        return prompt


    def start_conversation(self):
        """Start an interactive conversation loop."""
        print("Welcome! You can start asking questions about the system administration documentation. Type 'exit' to end the conversation.")

        while True:
            user_input = input("\nYour question: ").strip()

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye! Thank you for the conversation.")
                break

            response = self.query_system(user_input)
            print("\nAssistant:", response)

    def load_existing_db(self, persist_directory="./chroma_db"):
        """Load an existing Chroma database"""
        try:
            self.embeddings = HuggingFaceEmbeddings(model_name=self.embedding_model_name)
            self.db = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings
            )
            return "Existing database loaded! You can start asking questions."
        except Exception as e:
            logging.error(f"Error loading existing database: {e}", exc_info=True)
            return f"Error loading existing database: {e}"

# Example usage:
if __name__ == "__main__":
    rag_system = ConversationalRAG()
    print(rag_system.initialize_system()) # Assumes your documents are in a 'docs' folder
    rag_system.start_conversation()
