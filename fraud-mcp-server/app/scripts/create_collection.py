import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance
)

client = QdrantClient(
    host=os.getenv(
        "QDRANT_HOST",
        "qdrant"
    ),
    port=int(
        os.getenv(
            "QDRANT_PORT",
            "6333"
        )
    )
)
collections = client.get_collections()

exists = any(
    c.name == "customer_documents"
    for c in collections.collections
)

if not exists:
    client.create_collection(
        collection_name="customer_documents",
        vectors_config=VectorParams(
            size=1536,
            distance=Distance.COSINE
        )
    )

    print(
        "customer_documents collection created"
    )
else:
    print(
        "customer_documents collection already exists"
    )