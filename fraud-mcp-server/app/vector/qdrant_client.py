import os
from qdrant_client import QdrantClient


def get_qdrant_client():
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "qdrant"),
        port=int(os.getenv("QDRANT_PORT", "6333"))
    )