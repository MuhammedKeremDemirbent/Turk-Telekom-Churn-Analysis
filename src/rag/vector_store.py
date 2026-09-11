import json
from pathlib import Path

import faiss

from .embeddings import Embedder
from .models import Document, SearchResult


class FaissStore:
    def __init__(
        self,
        index: faiss.Index,
        documents: list[Document],
        embedder: Embedder,
    ) -> None:
        if index.ntotal != len(documents):
            raise ValueError(
                "FAISS indeksindeki vektör sayısı ile "
                "doküman sayısı uyuşmuyor."
            )

        self.index = index
        self.documents = documents
        self.embedder = embedder

    @classmethod
    def build(
        cls,
        documents: list[Document],
        embedder: Embedder,
    ) -> "FaissStore":
        if not documents:
            raise ValueError("İndeks oluşturmak için doküman gereklidir.")

        texts = [document.content for document in documents]
        vectors = embedder.embed(texts)

        # Cosine similarity için vektörleri normalize ediyoruz.
        faiss.normalize_L2(vectors)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        return cls(
            index=index,
            documents=documents,
            embedder=embedder,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        if not query.strip():
            return []

        if top_k < 1:
            raise ValueError("top_k pozitif olmalıdır.")

        query_vector = self.embedder.embed([query])
        faiss.normalize_L2(query_vector)

        result_count = min(top_k, len(self.documents))

        scores, indices = self.index.search(
            query_vector,
            result_count,
        )

        results: list[SearchResult] = []

        for score, document_index in zip(scores[0], indices[0]):
            if document_index < 0:
                continue

            results.append(
                SearchResult(
                    document=self.documents[int(document_index)],
                    score=float(score),
                )
            )

        return results

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        faiss.write_index(
            self.index,
            str(directory / "reference.index"),
        )

        payload = {
            "embedding_model": self.embedder.model,
            "documents": [
                {
                    "document_id": document.document_id,
                    "content": document.content,
                    "title": document.title,
                    "category": document.category,
                    "issue_code": document.issue_code,
                    "duplicate_ids": list(document.duplicate_ids),
                }
                for document in self.documents
            ],
        }

        metadata_path = directory / "documents.json"

        metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        directory: str | Path,
        embedder: Embedder,
    ) -> "FaissStore":
        directory = Path(directory)

        metadata_path = directory / "documents.json"
        index_path = directory / "reference.index"

        payload = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        saved_model = payload["embedding_model"]

        if saved_model != embedder.model:
            raise ValueError(
                f"İndeks {saved_model!r} modeliyle oluşturulmuş, "
                f"aktif model ise {embedder.model!r}."
            )

        documents = [
            Document(
                document_id=item["document_id"],
                content=item["content"],
                title=item.get("title", ""),
                category=item.get("category", ""),
                issue_code=item.get("issue_code", ""),
                duplicate_ids=tuple(item.get("duplicate_ids", [])),
            )
            for item in payload["documents"]
        ]

        index = faiss.read_index(str(index_path))

        return cls(
            index=index,
            documents=documents,
            embedder=embedder,
        )