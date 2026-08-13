import json
import uuid
from typing import (
    Any,
    AsyncContextManager,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
)

import numpy as np
from core import get_db
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from models.memory import BaseVectorModel
from repositories.vector_store_repository import VectorStoreRepository
from sqlalchemy.ext.asyncio import AsyncSession


class VectorStoreService:
    def __init__(
        self,
        session_factory: Optional[
            Callable[[], AsyncContextManager[AsyncSession]]
        ] = None,
        model_cls: Type[BaseVectorModel] = BaseVectorModel,
        embedding_function: Optional[Embeddings] = None,
        vector_repository: Optional[VectorStoreRepository] = None,
    ) -> None:
        self.session_factory = session_factory or get_db
        self.model_cls = model_cls
        self.embedding_function = embedding_function
        self.vector_repository = vector_repository or VectorStoreRepository(
            session_factory=self.session_factory
        )

    async def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        if not self.embedding_function:
            raise ValueError("Embedding function is required to add texts.")

        embeddings = self.embedding_function.embed_documents(texts)
        records: List[BaseVectorModel] = []

        for index, text_content in enumerate(texts):
            doc_id = str(uuid.uuid4())
            metadata = metadatas[index] if metadatas and index < len(metadatas) else {}
            embedding_json = json.dumps(embeddings[index])

            record = self.model_cls(
                id=doc_id,
                content=text_content,
                embedding=embedding_json,
                metadata_json=json.dumps(metadata),
            )
            records.append(record)

        return await self.vector_repository.add_vector_records(records)

    async def similarity_search(
        self,
        query: str,
        k: int = 3,
        filter: Optional[Mapping[str, Any]] = None,
    ) -> List[Document]:
        if not self.embedding_function:
            raise ValueError("Embedding function is required for similarity search.")

        query_embedding = np.array(
            self.embedding_function.embed_query(query), dtype=np.float32
        )
        query_norm = np.linalg.norm(query_embedding)

        instances = await self.vector_repository.get_all_vector_records(self.model_cls)

        scored_documents: List[tuple[Document, float]] = []
        for instance in instances:
            try:
                metadata = json.loads(instance.metadata_json or "{}")
            except Exception:
                metadata = {}

            if filter:
                matches_filter = True
                for field_key, expected_val in filter.items():
                    if isinstance(expected_val, dict) and "$gt" in expected_val:
                        if metadata.get(field_key, 0) <= expected_val["$gt"]:
                            matches_filter = False
                            break
                    elif metadata.get(field_key) != expected_val:
                        matches_filter = False
                        break
                if not matches_filter:
                    continue

            try:
                record_embedding = np.array(
                    json.loads(instance.embedding), dtype=np.float32
                )
                record_norm = np.linalg.norm(record_embedding)
                denominator = query_norm * record_norm
                similarity = (
                    (np.dot(query_embedding, record_embedding) / denominator)
                    if denominator > 0
                    else 0.0
                )
            except Exception:
                similarity = 0.0

            doc = Document(page_content=instance.content, metadata=metadata)
            scored_documents.append((doc, float(similarity)))

        scored_documents.sort(key=lambda item: item[1], reverse=True)
        return [doc for doc, _ in scored_documents[:k]]
