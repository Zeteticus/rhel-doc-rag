import React, { useState } from 'react';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState({
    retrievalDocs: 5,
    temperature: 0.7,
    maxTokens: 512
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:5000/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          top_k: settings.retrievalDocs,
          temperature: settings.temperature,
          max_tokens: settings.maxTokens
        }),
      });
      
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error:', error);
      setResult({
        answer: "An error occurred while processing your request. Please try again.",
        sources: []
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-content">
          <h1>Red Hat Documentation Assistant</h1>
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className="settings-button"
          >
            Settings
          </button>
        </div>
      </header>
      
      <main className="main-content">
        <form onSubmit={handleSubmit} className="search-form">
          <div className="search-container">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question about Red Hat documentation..."
              className="search-input"
            />
            <button 
              type="submit" 
              className="search-button"
              disabled={loading || !query.trim()}
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
        </form>
        
        {showSettings && (
          <div className="settings-panel">
            <h2>Search Settings</h2>
            <div className="settings-grid">
              <div className="setting-item">
                <label>
                  Retrieved Documents: {settings.retrievalDocs}
                </label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={settings.retrievalDocs}
                  onChange={(e) => setSettings({...settings, retrievalDocs: parseInt(e.target.value)})}
                />
              </div>
              
              <div className="setting-item">
                <label>
                  Temperature: {settings.temperature}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) => setSettings({...settings, temperature: parseFloat(e.target.value)})}
                />
              </div>
              
              <div className="setting-item">
                <label>
                  Max Response Length: {settings.maxTokens} tokens
                </label>
                <input
                  type="range"
                  min="128"
                  max="1024"
                  step="128"
                  value={settings.maxTokens}
                  onChange={(e) => setSettings({...settings, maxTokens: parseInt(e.target.value)})}
                />
              </div>
            </div>
          </div>
        )}
        
        {result && (
          <div className="results-container">
            <div className="answer-container">
              <h2>Answer</h2>
              <div className="answer-content">
                {result.answer}
              </div>
            </div>
            
            <div className="sources-container">
              <h2>Sources</h2>
              <div className="sources-list">
                {result.sources.map((source, index) => (
                  <div key={index} className="source-item">
                    <h3>{source.title}</h3>
                    <p>{source.text.substring(0, 150)}...</p>
                    <a 
                      href={source.source} 
                      target="_blank" 
                      rel="noopener noreferrer"
                    >
                      View Source →
                    </a>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
      
      <footer className="footer">
        <div className="footer-content">
          Red Hat Documentation RAG System | RHEL 9.6 | Powered by Podman
        </div>
      </footer>
    </div>
  );
}

export default App;
