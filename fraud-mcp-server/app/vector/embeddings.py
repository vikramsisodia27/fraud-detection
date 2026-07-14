from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"


class LocalEmbeddings:
    """Wrapper around SentenceTransformer that exposes embed_query()
    so callers (rag_service, load_documents, etc.) don't change their API."""

    def __init__(self):
        self.model = SentenceTransformer(_MODEL_NAME)

    def embed_query(self, text: str):
        return self.model.encode(text).tolist()


def get_embeddings():
    return LocalEmbeddings()