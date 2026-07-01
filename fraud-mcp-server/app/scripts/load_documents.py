import uuid
import os

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from langchain_openai import OpenAIEmbeddings

from customer_documents import documents

client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "qdrant"),
    port=int(os.getenv("QDRANT_PORT", "6333"))
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY")
)

points = []

for doc in documents:

    vector = embeddings.embed_query(
        doc["text"]
    )

    points.append(
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=doc
        )
    )

client.upsert(
    collection_name="customer_documents",
    points=points
)

print("Documents loaded.")