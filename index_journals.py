import json
import os
import nltk
from nltk.tokenize import word_tokenize
import pinecone
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from typing import List, Dict, Any
import argparse
import tiktoken
import sys

# Load environment variables
load_dotenv()

# Initialize OpenAI and Pinecone
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(
    api_key=api_key,
)  # This will automatically use OPENAI_API_KEY from environment
pc = pinecone.Pinecone(
    api_key=os.getenv("PINECONE_API_KEY"),
)

# Download required NLTK data
nltk.download('punkt_tab', quiet=True)

# Constants
INDEX_NAME = "emotional-journals"
DIMENSION = 1536  # Dimension for text-embedding-ada-002
BATCH_SIZE = 10  # Reduced batch size to stay under 2MB limit
PROGRESS_FILE = "indexing_progress.json"
MAX_TOKENS = 8000  # Conservative limit for text-embedding-ada-002 (8192 max)
MAX_REQUEST_SIZE = 1.8 * 1024 * 1024  # 1.8MB to be safe (Pinecone limit is 2MB)

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using tiktoken."""
    encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    return len(encoding.encode(text))

def split_into_chunks(text: str, max_tokens: int = MAX_TOKENS) -> List[str]:
    """Split text into chunks that fit within token limit."""
    if count_tokens(text) <= max_tokens:
        return [text]
        
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    # Split into sentences first
    sentences = nltk.sent_tokenize(text, language='russian')
    
    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        
        # If a single sentence is too long, split it into words
        if sentence_tokens > max_tokens:
            words = word_tokenize(sentence)
            for word in words:
                word_tokens = count_tokens(word)
                if current_tokens + word_tokens > max_tokens:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [word]
                    current_tokens = word_tokens
                else:
                    current_chunk.append(word)
                    current_tokens += word_tokens
        # If adding this sentence would exceed the limit, start a new chunk
        elif current_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def get_embedding(text: str) -> List[float]:
    """Get embedding for a text using OpenAI's text-embedding-ada-002 model."""
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK."""
    return nltk.sent_tokenize(text, language='russian')

def split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs."""
    # Split by double newlines and clean up
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return paragraphs

def create_metadata(entry_date: str, granularity: str, text: str, index: int = None) -> Dict[str, Any]:
    """Create metadata for a journal entry."""
    metadata = {
        "date": entry_date,
        "granularity": granularity,
        "text_length": len(text),
        "created_at": datetime.utcnow().isoformat()
    }
    if index is not None:
        metadata["index"] = index
    return metadata

def process_journal_entry(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a single journal entry into different granularity levels."""
    date = entry.get("date", "")
    content = entry.get("emotional_content", "")
    
    vectors = []
    
    # Process whole entry, but still need to split because might be too long
    if content.strip():
        # Split content into chunks that fit within model context window
        chunks = split_into_chunks(content)
        
        # Create vector for each chunk
        for i, chunk in enumerate(chunks):
            vectors.append({
                "id": f"{date}_whole_chunk_{i}",
                "values": get_embedding(chunk),
                "metadata": create_metadata(date, "whole_chunk", chunk, i)
            })
    
    # Process paragraphs
    paragraphs = split_into_paragraphs(content)
    for i, para in enumerate(paragraphs):
        if para.strip():
            # Split paragraph into chunks if needed
            chunks = split_into_chunks(para)
            for j, chunk in enumerate(chunks):
                vectors.append({
                    "id": f"{date}_para_{i}_chunk_{j}",
                    "values": get_embedding(chunk),
                    "metadata": create_metadata(date, "paragraph_chunk", chunk, f"{i}_{j}")
                })
    
    # Process sentences
    sentences = split_into_sentences(content)
    for i, sent in enumerate(sentences):
        if sent.strip():
            # Split sentence into chunks if needed (rare but possible)
            chunks = split_into_chunks(sent)
            for j, chunk in enumerate(chunks):
                vectors.append({
                    "id": f"{date}_sent_{i}_chunk_{j}",
                    "values": get_embedding(chunk),
                    "metadata": create_metadata(date, "sentence_chunk", chunk, f"{i}_{j}")
                })
    
    return vectors

def load_progress() -> Dict[str, Any]:
    """Load progress from file if it exists."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"processed_entries": [], "last_batch": []}

def save_progress(processed_entries: List[str], last_batch: List[Dict[str, Any]] = None):
    """Save current progress to file."""
    progress = {
        "processed_entries": processed_entries,
        "last_batch": last_batch or []
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def estimate_vector_size(vector: Dict[str, Any]) -> int:
    """Estimate the size of a vector in bytes."""
    # Rough estimation: id + values + metadata
    id_size = len(vector["id"].encode('utf-8'))
    values_size = len(vector["values"]) * 4  # float32 = 4 bytes
    metadata_size = len(json.dumps(vector["metadata"]).encode('utf-8'))
    return id_size + values_size + metadata_size

def get_safe_batch(vectors: List[Dict[str, Any]], max_size: int = MAX_REQUEST_SIZE) -> List[Dict[str, Any]]:
    """Get a batch of vectors that fits within the size limit."""
    if not vectors:
        return []
        
    batch = []
    current_size = 0
    
    for vector in vectors:
        vector_size = estimate_vector_size(vector)
        if current_size + vector_size > max_size:
            break
        batch.append(vector)
        current_size += vector_size
    
    return batch

def main():
    parser = argparse.ArgumentParser(description='Index emotional journals in Pinecone')
    parser.add_argument('--clear', action='store_true', help='Clear existing index and progress')
    args = parser.parse_args()

    # Create or get Pinecone index
    if not INDEX_NAME in [index.name for index in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric="cosine",
            spec=pinecone.ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    
    index = pc.Index(INDEX_NAME)
    
    # Only clear index and progress if --clear flag is used
    if args.clear:
        try:
            index.delete(delete_all=True)
            print("Cleared existing vectors from index")
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
                print("Cleared progress file")
        except Exception as e:
            if "Namespace not found" in str(e):
                print("Index is empty, proceeding with new data")
            else:
                raise e
    
    # Load journal entries and progress
    print("Loading journal entries...")
    with open("journal_entries.json", "r") as f:
        journal_entries = json.load(f)
    
    progress = load_progress()
    processed_entries = set(progress["processed_entries"])
    all_vectors = progress["last_batch"]  # Resume with any vectors from last batch
    
    print(f"Resuming from {len(processed_entries)} processed entries")
    
    # Process entries in batches
    print("Processing journal entries...")
    try:
        for entry in tqdm(journal_entries):
            date = entry.get("date")
            # skip entry if date is null or no emotional content or already processed
            if date is None or entry.get("emotional_content") is None or date in processed_entries:
                continue
                
            vectors = process_journal_entry(entry)
            all_vectors.extend(vectors)
            processed_entries.add(date)
            
            # Save progress after each entry
            save_progress(list(processed_entries), all_vectors)
            
            # Upload in batches that respect size limits
            while all_vectors:
                batch = get_safe_batch(all_vectors)
                if not batch:
                    print("\nWarning: Single vector too large, skipping...")
                    all_vectors = all_vectors[1:]  # Skip the problematic vector
                    continue
                    
                try:
                    index.upsert(vectors=batch)
                    all_vectors = all_vectors[len(batch):]  # Remove processed vectors
                    save_progress(list(processed_entries))  # Clear last batch after successful upload
                except Exception as e:
                    if "Request size" in str(e):
                        # If we still hit size limit, reduce batch size and retry
                        print(f"\nReducing batch size due to request size limit...")
                        all_vectors = all_vectors[1:]  # Skip one vector and try again
                    else:
                        raise e
        
        print("Indexing complete!")
        # Only clean up progress file if we processed everything
        if len(processed_entries) == len([e for e in journal_entries if e.get("date") and e.get("emotional_content")]):
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
                print("All entries processed, progress file cleaned up")
            
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        print(f"Progress saved. You can resume from where you left off by running the script again.")
        raise e

if __name__ == "__main__":
    main() 