from typing import List, Optional

from langchain_core.embeddings import Embeddings


class OpenSourceEmbeddingService(Embeddings):
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _hash_vector(self, text: str) -> List[float]:
        tokens = text.lower().split()
        vector = [0.0] * self.dimension
        if not tokens:
            return vector

        for i, token in enumerate(tokens):
            index = hash(token) % self.dimension
            vector[index] += 1.0
            if i < len(tokens) - 1:
                bigram = f"{token}_{tokens[i + 1]}"
                bigram_index = hash(bigram) % self.dimension
                vector[bigram_index] += 0.5

        sum_of_squares = sum(val * val for val in vector)
        if sum_of_squares > 0:
            norm = sum_of_squares**0.5
            vector = [val / norm for val in vector]

        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vector(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._hash_vector(text)


class HuggingFaceEmbeddingService(Embeddings):
    _shared_embeddings: Optional[Embeddings] = None
    _shared_fallback: Optional[Embeddings] = None

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> None:
        import os

        self.model_name = model_name

        if HuggingFaceEmbeddingService._shared_fallback is None:
            HuggingFaceEmbeddingService._shared_fallback = OpenSourceEmbeddingService(
                dimension=384
            )

        if HuggingFaceEmbeddingService._shared_embeddings is None:
            hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN", "")
            model_kwargs = {"token": hf_token} if hf_token else {}

            try:
                from langchain_huggingface import HuggingFaceEmbeddings

                HuggingFaceEmbeddingService._shared_embeddings = HuggingFaceEmbeddings(
                    model_name=self.model_name,
                    model_kwargs=model_kwargs if model_kwargs else None,
                )
            except Exception:
                try:
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                    HuggingFaceEmbeddingService._shared_embeddings = (
                        HuggingFaceEmbeddings(
                            model_name=self.model_name,
                            model_kwargs=model_kwargs if model_kwargs else None,
                        )
                    )
                except Exception:
                    pass

        self._fallback_service = HuggingFaceEmbeddingService._shared_fallback
        self._huggingface_embeddings = HuggingFaceEmbeddingService._shared_embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._huggingface_embeddings is not None:
            try:
                return self._huggingface_embeddings.embed_documents(texts)
            except Exception:
                pass
        return self._fallback_service.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        if self._huggingface_embeddings is not None:
            try:
                return self._huggingface_embeddings.embed_query(text)
            except Exception:
                pass
        return self._fallback_service.embed_query(text)


# Backwards compatibility aliases
OpenSourceEmbeddings = OpenSourceEmbeddingService
HuggingFaceEmbeddingModel = HuggingFaceEmbeddingService
