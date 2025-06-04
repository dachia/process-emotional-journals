import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
import tiktoken
from openai import OpenAI
import pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
INDEX_NAME = "emotional-journals"
DIMENSION = 1536  # Dimension for text-embedding-ada-002
MAX_TOKENS = 8000  # Conservative limit for text-embedding-ada-002
MAX_REQUEST_SIZE = 1.8 * 1024 * 1024  # 1.8MB to be safe (Pinecone limit is 2MB)

# Initialize OpenAI and Pinecone clients
def get_openai_client() -> OpenAI:
    """Get initialized OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)

def get_pinecone_index():
    """Get initialized Pinecone index."""
    pc = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index(INDEX_NAME)

# Date handling
def date_to_timestamp(date_str: str) -> int:
    """Convert date string (YYYY-MM-DD) to Unix timestamp."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return int(dt.timestamp())

def timestamp_to_date(timestamp: int) -> str:
    """Convert Unix timestamp to date string (YYYY-MM-DD)."""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

# Text processing
def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using tiktoken."""
    encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    return len(encoding.encode(text))

def get_embedding(text: str) -> List[float]:
    """Get embedding for a text using OpenAI's text-embedding-ada-002 model."""
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

# File operations
def save_json(data: Any, filename: str) -> None:
    """Save data to a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filename: str) -> Any:
    """Load data from a JSON file."""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def ensure_directory(directory: str) -> None:
    """Ensure a directory exists, create if it doesn't."""
    Path(directory).mkdir(parents=True, exist_ok=True)

# Search utilities
def search_pinecone(
    query: str,
    granularity: Literal['whole_chunk', 'paragraph_chunk', 'sentence_chunk'],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_k: int = 10
) -> List[Dict]:
    """Search Pinecone index with optional date filtering."""
    index = get_pinecone_index()
    query_embedding = get_embedding(query)
    
    # Build filter
    filter_dict = {"granularity": granularity}
    if start_date and end_date:
        filter_dict["timestamp"] = {
            "$gte": date_to_timestamp(start_date),
            "$lte": date_to_timestamp(end_date)
        }
    
    # Search in Pinecone
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict
    )
    
    # Format results
    return [{
        'text': match.metadata['text'],
        'date': match.metadata['date'],
        'similarity': match.score,
        'metadata': match.metadata
    } for match in results.matches]

# Journal processing constants
SECTION_HEADERS = [
    '## 🌀What do I feel right this moment?',
    '## 🔍Where is it coming from?',
    '## 🛤️Do I need to solve it? How?',
    '## emotion dump',
    '### Journal'
]

SECTION_SUBHEADERS = [
    '> Unfiltered. Go at it. Dump what you feel. It\'s for me. Deepest-darkest',
    '> Where the feeling is coming from? What\'s behind it? Don\'t overthink, just dig',
    '> Do I need to find a path forward? Is knowledge enough?',
]

def is_section_header(line: str) -> bool:
    """Check if a line is a section header."""
    return line.strip() in SECTION_HEADERS

def is_section_subheader(line: str) -> bool:
    """Check if a line is a section subheader."""
    return line.strip() in SECTION_SUBHEADERS

def is_task_line(line: str) -> bool:
    """Check if a line is a task line."""
    return line.strip().startswith('- [') or line.strip().startswith('\t- [') 