from collections.abc import Sequence

import numpy as np
from openai import OpenAI


class Embedder:
    def __init__(
        self,
        client: OpenAI,
        model: str = "BAAI/bge-m3",
        batch_size: int = 64,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size pozitif olmalıdır.")

        self.client = client
        self.model = model
        self.batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        vectors: list[list[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])

            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )

            ordered_items = sorted(
                response.data,
                key=lambda item: item.index,
            )

            vectors.extend(item.embedding for item in ordered_items)

        matrix = np.asarray(vectors, dtype=np.float32)

        if matrix.ndim != 2:
            raise RuntimeError("Embedding sonucu iki boyutlu değil.")

        if matrix.shape[0] != len(texts):
            raise RuntimeError(
                "Embedding API beklenmeyen sayıda vektör döndürdü."
            )

        return matrix