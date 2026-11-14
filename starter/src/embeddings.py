"""Local sentence-transformers embedding adapter."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, question: str) -> list[float]:
        ...


class MyEmbedder:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Install the local embedding dependency with "
                "`python -m pip install -r requirements.txt`."
            ) from error

        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")
        dimensions = self.model.get_embedding_dimension()
        if not dimensions:
            raise RuntimeError(f"Embedding model has no declared dimensions: {model_name}")
        self.dimensions = int(dimensions)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result = vectors.tolist()
        if len(result) != len(texts) or any(len(vector) != self.dimensions for vector in result):
            raise RuntimeError("Embedding provider returned an unexpected vector shape")
        return result

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, question: str) -> list[float]:
        vectors = self._encode([question])
        return vectors[0]
