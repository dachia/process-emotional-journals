import openai
import pinecone
import os
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Connect to Pinecone
pk = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pk.Index('emotional-journals')

def create_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def date_to_timestamp(date_str):
    """Convert date string (YYYY-MM-DD) to Unix timestamp."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return int(dt.timestamp())

def search_phase(query_text, start_date, end_date, top_k=10):
    embedding = create_embedding(query_text)
    # Convert dates to timestamps for Pinecone filtering
    start_timestamp = date_to_timestamp(start_date)
    end_timestamp = date_to_timestamp(end_date)
    
    result = index.query(
        vector=embedding,
        top_k=top_k,
        filter={
            "timestamp": {
                "$gte": start_timestamp,
                "$lte": end_timestamp
            },
            "granularity": "paragraph_chunk"
        },
        include_metadata=True
    )
    # Return list of (date, text) tuples using the string date from metadata
    return [
        (match['metadata'].get('date', ''), match['metadata']['text'])
        for match in result['matches']
    ]
# early_texts = [
#     "борьба с собой и своими чувствами",
#     "стыд, вина, неприятие себя",
#     "страх, беспомощность, разобщенность"
# ]
# middle_texts = [
#     "путаница, сомнения, поиски смысла",
#     "первые попытки понять и принять себя",
#     "наблюдение за собой и своими чувствами"
# ]
# late_texts = [
#     "осознание и принятие себя таким, какой есть",
#     "выбор себя, внутреннее согласие",
#     "разрешение себе чувствовать без борьбы"
# ]

# # Early Phase
# early_entries = search_phase(
#     query_text=early_texts,
#     start_date="2023-10-24",
#     end_date="2024-07-01",
#     top_k=20
# )

# # Middle Phase
# middle_entries = search_phase(
#     query_text=middle_texts,
#     start_date="2024-07-02",
#     end_date="2025-02-15",
#     top_k=20
# )

# Late Phase
# late_entries = search_phase(
#     query_text=late_texts,
#     start_date="2025-02-16",
#     end_date="2025-06-02",
#     top_k=20
# )
# Save results to files
def save_entries(filename, entries):
    with open(filename, 'w', encoding='utf-8') as f:
        for date, text in entries:
            f.write(f"Date: {date}\n{text.strip()}\n\n")

# save_entries('early_phase_entries.txt', early_entries)
# save_entries('middle_phase_entries.txt', middle_entries)
# save_entries('late_phase_entries.txt', late_entries)


# early_entries = search_phase(
#     query_text=early_texts,
#     start_date="2023-10-24",
#     end_date="2024-07-01",
#     top_k=20
# )

# # Middle Phase
# middle_entries = search_phase(
#     query_text=middle_texts,
#     start_date="2024-07-02",
#     end_date="2025-02-15",
#     top_k=20
# )

# Late Phase
# late_entries = search_phase(
#     query_text=late_texts,
#     start_date="2025-02-16",
#     end_date="2025-06-02",
#     top_k=20
# )

search_terms = [
    "я размышлял о себе",                   # self-reflection
    "я решил принять себя",                 # decision to accept myself
    "я разрешил себе чувствовать",           # allowance to feel
    "я отпустил ситуацию",                   # letting go
    "я начал писать чтобы понять себя",      # journaling
    "я учился принимать свои чувства",       # learning to accept feelings
    "я заботился о себе маленькими шагами",  # small self-care
    "я выбрал себя",                         # choosing self
    "я заметил свой старый паттерн"          # noticing old pattern
]


found_terms = {}
for term in search_terms:
    result = search_phase(
        query_text=[term],
        start_date="2023-10-24",
        end_date="2024-07-01",
        top_k=20
    )
    found_terms[term] = result
    
## save entries to single file grouped by term
with open('found_terms.txt', 'w', encoding='utf-8') as f:
    for term, matches in found_terms.items():
        f.write(f"{term}\n")
        for date, text in matches:
            f.write(f"{date}: {text}\n")
            f.write("\n")