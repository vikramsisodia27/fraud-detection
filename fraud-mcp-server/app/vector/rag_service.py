import logging
from typing import List, Dict

embeddings = get_embeddings()
qdrant = get_qdrant_client()

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue
)




logger = logging.getLogger(__name__)

COLLECTION_NAME = "customer_documents"


class RagService:

    @staticmethod
    def retrieve_customer_context(
            customer_id: str,
            limit: int = 5
    ) -> List[Dict]:

        try:
            query = f"""
            Historical fraud information,
            investigation reports,
            analyst notes,
            SAR reports,
            emails and KYC documents
            for customer {customer_id}
            """

            query_vector = embeddings.embed_query(
                query
            )

            results = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="customer_id",
                            match=MatchValue(
                                value=customer_id
                            )
                        )
                    ]
                ),
                limit=limit
            )

            documents = []

            for result in results:

                payload = result.payload

                documents.append(
                    {
                        "score": result.score,
                        "document_id":
                            payload.get("id"),
                        "customer_id":
                            payload.get("customer_id"),
                        "document_type":
                            payload.get(
                                "document_type"
                            ),
                        "created_date":
                            payload.get(
                                "created_date"
                            ),
                        "text":
                            payload.get("text")
                    }
                )

            logger.info(
                "Retrieved %s documents for customer %s",
                len(documents),
                customer_id
            )

            return documents

        except Exception:
            logger.exception(
                "Failed retrieving customer context"
            )
            return []

    @staticmethod
    def build_customer_context(
            customer_id: str,
            limit: int = 5
    ) -> str:

        documents = (
            RagService
            .retrieve_customer_context(
                customer_id,
                limit
            )
        )

        if not documents:
            return (
                f"No historical information "
                f"found for customer "
                f"{customer_id}"
            )

        context = []

        for doc in documents:

            context.append(
                f"""
Document Type:
{doc['document_type']}

Created Date:
{doc['created_date']}

Content:
{doc['text']}
"""
            )

        return "\n".join(context)