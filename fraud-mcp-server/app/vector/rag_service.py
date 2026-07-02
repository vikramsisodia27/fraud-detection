import logging
from functools import lru_cache
from typing import List, Dict

from app.vector.embeddings import get_embeddings
from app.vector.qdrant_client import get_qdrant_client

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "customer_documents"


@lru_cache(maxsize=1)
def _embeddings_client():
    """Singleton — avoid re-creating an HTTP client on every call."""
    return get_embeddings()


@lru_cache(maxsize=1)
def _qdrant_client():
    """Singleton — avoid re-creating a connection on every call."""
    return get_qdrant_client()


class RagService:

    @staticmethod
    def retrieve_customer_context(
            customer_id: str,
            limit: int = 5,
            per_type_cap: int = 2,
    ) -> List[Dict]:
        """
        Retrieve top historical documents for a customer, capped per
        document_type so no single duplicated/near-duplicate type can
        crowd out other evidence categories (e.g. two similar SAR
        reports pushing out KYC/email documents entirely).
        """
        try:
            embeddings = _embeddings_client()
            qdrant = _qdrant_client()

            query = f"""
            Historical fraud information,
            investigation reports,
            analyst notes,
            SAR reports,
            emails and KYC documents
            for customer {customer_id}
            """

            query_vector = embeddings.embed_query(query)

            # over-fetch, then diversify/dedupe client-side
            results = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="customer_id",
                            match=MatchValue(value=customer_id),
                        )
                    ]
                ),
                limit=max(limit * 4, 20),
            )

            seen_text = set()
            per_type_count: Dict[str, int] = {}
            documents: List[Dict] = []

            for result in results:
                payload = result.payload or {}
                text = payload.get("text", "")
                doc_type = payload.get("document_type", "unknown")

                # dedupe near-identical content (same text = same doc re-ingested)
                if text in seen_text:
                    continue

                # cap per document_type so no one type crowds out others
                if per_type_count.get(doc_type, 0) >= per_type_cap:
                    continue

                seen_text.add(text)
                per_type_count[doc_type] = per_type_count.get(doc_type, 0) + 1

                documents.append({
                    "score": result.score,
                    "document_id": payload.get("id"),
                    "customer_id": payload.get("customer_id"),
                    "document_type": doc_type,
                    "created_date": payload.get("created_date"),
                    "text": text,
                })

                if len(documents) >= limit:
                    break

            logger.info(
                "Retrieved %s documents (%s types) for customer %s",
                len(documents), len(per_type_count), customer_id,
            )

            return documents

        except Exception:
            logger.exception("Failed retrieving customer context")
            return []

    @staticmethod
    def format_documents(documents: List[Dict], customer_id: str) -> str:
        if not documents:
            return f"No historical information found for customer {customer_id}"

        blocks = []
        for doc in documents:
            blocks.append(
                f"""
Document Type: {doc['document_type']}
Created Date: {doc['created_date']}
Similarity Score: {round(doc['score'], 4)}

Content:
{doc['text']}
"""
            )
        return "\n".join(blocks)

    @staticmethod
    def build_customer_context(customer_id: str, limit: int = 5) -> str:
        documents = RagService.retrieve_customer_context(customer_id, limit)
        return RagService.format_documents(documents, customer_id)