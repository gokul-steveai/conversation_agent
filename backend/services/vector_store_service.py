import json
import uuid
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    Union,
)

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from models.memory import BaseVectorModel
from repositories.vector_store_repository import VectorStoreRepository


class VectorStoreService:
    def __init__(
        self,
        vector_repository: VectorStoreRepository,
        model_cls: Type[BaseVectorModel] = BaseVectorModel,
        embedding_function: Optional[Embeddings] = None,
    ) -> None:
        self._vector_repository = vector_repository
        self.model_cls = model_cls
        self.embedding_function = embedding_function

    async def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ) -> List[str]:
        if not self.embedding_function:
            raise ValueError("Embedding function is required to add texts.")

        if not texts:
            return []

        active_version = getattr(self.embedding_function, "version", "default")

        if metadatas is None:
            formatted_metadatas: List[Dict[str, Any]] = [{} for _ in texts]
        elif isinstance(metadatas, dict):
            formatted_metadatas = [dict(metadatas) for _ in texts]
        elif isinstance(metadatas, list):
            if len(metadatas) == 1:
                formatted_metadatas = [dict(metadatas[0]) for _ in texts]
            elif len(metadatas) == len(texts):
                formatted_metadatas = metadatas
            else:
                raise ValueError(
                    f"Length mismatch: {len(texts)} texts provided, but metadatas list has length {len(metadatas)}."
                )
        else:
            formatted_metadatas = [{} for _ in texts]

        embeddings = self.embedding_function.embed_documents(texts)
        records: List[BaseVectorModel] = []

        for index, text_content in enumerate(texts):
            doc_id = str(uuid.uuid4())
            metadata = dict(formatted_metadatas[index])
            metadata["_embedding_version"] = active_version
            embedding_json = json.dumps(embeddings[index])

            record = self.model_cls(
                id=doc_id,
                content=text_content,
                embedding=embedding_json,
                metadata_json=json.dumps(metadata),
            )
            records.append(record)

        return await self._vector_repository.add_vector_records(records)

    async def similarity_search(
        self,
        query: str,
        k: int = 3,
        filter: Optional[Mapping[str, Any]] = None,
    ) -> List[Document]:
        if not self.embedding_function:
            raise ValueError("Embedding function is required for similarity search.")

        active_version = getattr(self.embedding_function, "version", "default")
        query_embedding = np.array(
            self.embedding_function.embed_query(query), dtype=np.float32
        )
        query_norm = np.linalg.norm(query_embedding)

        candidate_limit = max(100, k * 10)
        instances = await self._vector_repository.get_candidate_vector_records(
            self.model_cls, limit=candidate_limit
        )

        scored_documents: List[tuple[Document, float]] = []
        for instance in instances:
            try:
                metadata = json.loads(instance.metadata_json or "{}")
            except Exception:
                metadata = {}

            # Skip vector records from incompatible embedding spaces/versions
            stored_version = metadata.get("_embedding_version")
            if stored_version and stored_version != active_version:
                continue

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
