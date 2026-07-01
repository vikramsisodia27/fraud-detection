from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
import os

client = QdrantClient(
    host="localhost",
    port=6333
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY")
)

query = """
historical fraud cases
for customer CUST-1001
"""

query_vector = embeddings.embed_query(
    query
)

results = client.search(
    collection_name="customer_documents",
    query_vector=query_vector,
    limit=5
)

for result in results:
    print(result.payload)