import hashlib
import os

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.vector.embeddings import get_embeddings
from customer_documents import documents

client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "qdrant"),
    port=int(os.getenv("QDRANT_PORT", "6333"))
)

embeddings = get_embeddings()


def deterministic_id(doc: dict) -> str:
    """
    Stable ID derived from customer_id + document_type + text hash.
    Re-running this script now UPSERTS in place instead of creating
    duplicate points with fresh random UUIDs.
    """
    key = f"{doc['customer_id']}:{doc['document_type']}:{doc['text']}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


points = []

for doc in documents:
    vector = embeddings.embed_query(doc["text"])
    points.append(
        PointStruct(
            id=deterministic_id(doc),
            vector=vector,
            payload=doc,
        )
    )

client.upsert(
    collection_name="customer_documents",
    points=points,
)

print(f"Upserted {len(points)} documents (idempotent).")