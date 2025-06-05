import os
import requests
import markdown
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Environment variables
RAG_SERVICE_HOST = os.environ.get('RAG_SERVICE_HOST', 'localhost')
RAG_SERVICE_PORT = os.environ.get('RAG_SERVICE_PORT', '5000')
RAG_SERVICE_URL = f"http://{RAG_SERVICE_HOST}:{RAG_SERVICE_PORT}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query():
    data = request.json
    query_text = data.get('query', '')
    max_results = data.get('max_results', 5)
    
    try:
        # Send query to RAG service
        response = requests.post(
            f"{RAG_SERVICE_URL}/query",
            json={"query": query_text, "max_results": max_results}
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"RAG service error: {response.text}"}), 500
        
        result = response.json()
        
        # Convert answer from markdown to HTML if needed
        if query_text.strip():
            result['answer_html'] = markdown.markdown(result['answer'])
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process', methods=['POST'])
def process_documents():
    try:
        response = requests.post(f"{RAG_SERVICE_URL}/process_documents", json={})
        
        if response.status_code != 200:
            return jsonify({"error": f"Processing error: {response.text}"}), 500
        
        return jsonify(response.json())
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
