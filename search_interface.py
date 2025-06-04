import json
import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import pinecone
from dotenv import load_dotenv
from typing import List, Dict, Literal
import tiktoken
from utils import search_pinecone, ensure_directory

# Load environment variables
load_dotenv()

# Initialize OpenAI and Pinecone
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=api_key)

pc = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Constants
INDEX_NAME = "emotional-journals"
DIMENSION = 1536  # Dimension for text-embedding-ada-002

app = Flask(__name__)

# Initialize Pinecone index
index = pc.Index(INDEX_NAME)

def get_embedding(text: str) -> List[float]:
    """Get embedding for a text using OpenAI's text-embedding-ada-002 model."""
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def search(query: str, granularity: Literal['whole_chunk', 'paragraph_chunk', 'sentence_chunk'], top_k: int = 10) -> List[Dict]:
    # Get query embedding
    query_embedding = get_embedding(query)
    
    # Search in Pinecone
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter={
            "granularity": granularity
        }
    )
    
    # Format results
    formatted_results = []
    print(results)
    for match in results.matches:
        formatted_results.append({
            'text': match.metadata['text'],
            'date': match.metadata['date'],
            'similarity': match.score,
            'metadata': match.metadata
        })
    
    return formatted_results

@app.route('/')
def home():
    return render_template('search.html')

@app.route('/search', methods=['POST'])
def search_endpoint():
    data = request.json
    query = data.get('query', '')
    granularity = data.get('granularity', 'paragraphs')
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Map frontend granularity to Pinecone granularity
    granularity_map = {
        'journals': 'whole_chunk',
        'paragraphs': 'paragraph_chunk',
        'sentences': 'sentence_chunk'
    }
    
    if granularity not in granularity_map:
        return jsonify({'error': 'Invalid granularity'}), 400
    
    results = search_pinecone(query, granularity_map[granularity])
    return jsonify({'results': results})

# Create templates directory and search.html
ensure_directory('templates')

# Create the HTML template
with open('templates/search.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Journal Search</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        .result-card {
            transition: all 0.3s ease;
        }
        .result-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">Journal Search</h1>
        
        <div class="max-w-2xl mx-auto bg-white rounded-lg shadow-md p-6 mb-8">
            <div class="flex flex-col space-y-4">
                <input type="text" id="searchInput" 
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                       placeholder="Enter your search query...">
                
                <div class="flex space-x-4">
                    <select id="granularity" class="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        <option value="paragraphs">Paragraphs</option>
                        <option value="sentences">Sentences</option>
                        <option value="journals">Whole Journals</option>
                    </select>
                    
                    <button onclick="performSearch()" 
                            class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                        Search
                    </button>
                </div>
            </div>
        </div>
        
        <div id="results" class="max-w-4xl mx-auto space-y-4">
            <!-- Results will be inserted here -->
        </div>
    </div>

    <script>
        async function performSearch() {
            const query = document.getElementById('searchInput').value;
            const granularity = document.getElementById('granularity').value;
            const resultsDiv = document.getElementById('results');
            
            if (!query) {
                alert('Please enter a search query');
                return;
            }
            
            resultsDiv.innerHTML = '<div class="text-center"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div></div>';
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query, granularity }),
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    displayResults(data.results);
                } else {
                    resultsDiv.innerHTML = `<div class="text-red-500 text-center">${data.error}</div>`;
                }
            } catch (error) {
                resultsDiv.innerHTML = '<div class="text-red-500 text-center">An error occurred while searching</div>';
            }
        }
        
        function displayResults(results) {
            const resultsDiv = document.getElementById('results');
            
            if (results.length === 0) {
                resultsDiv.innerHTML = '<div class="text-center text-gray-500">No results found</div>';
                return;
            }
            
            resultsDiv.innerHTML = results.map((result, index) => `
                <div class="result-card bg-white rounded-lg shadow-md p-6 hover:shadow-lg">
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-sm text-gray-500">${result.date}</span>
                        <span class="text-sm text-blue-500">Similarity: ${(result.similarity * 100).toFixed(1)}%</span>
                    </div>
                    <p class="text-gray-800 whitespace-pre-wrap">${result.text}</p>
                </div>
            `).join('');
        }
        
        // Allow search on Enter key
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("Starting web server...")
    app.run(host='0.0.0.0', port=5000, debug=True) 