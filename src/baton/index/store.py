"""조각을 벡터로 바꿔 저장하고, 사용자 본인 범위 안에서만 찾는다."""

from dataclasses import dataclass, fields
from typing import Protocol

import chromadb

from baton.index.chunker import Chunk

COLLECTION = "chunks"
EMBEDDING_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 64


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    """메일 내용이 서버 밖으로 나가지 않도록 임베딩은 이 컴퓨터에서 계산한다."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None

    def embed(self, texts):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(texts, normalize_embeddings=True, batch_size=8).tolist()


@dataclass
class Hit:
    chunk: Chunk
    score: float


class MailIndex:
    def __init__(self, path: str, embedder: Embedder):
        client = chromadb.PersistentClient(path=path)
        self.collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        self.embedder = embedder

    def add(self, chunks: list[Chunk], owner_id: str) -> None:
        """같은 메일을 다시 넣어도 중복되지 않는다. 사용자가 달라도 서로 덮어쓰지 않는다."""
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]
            self.collection.upsert(
                ids=[f"{owner_id}:{chunk.id}" for chunk in batch],
                embeddings=self.embedder.embed([chunk.text for chunk in batch]),
                documents=[chunk.text for chunk in batch],
                metadatas=[{**_meta(chunk), "owner_id": owner_id} for chunk in batch],
            )

    def search(self, query: str, owner_id: str, k: int = 5) -> list[Hit]:
        """owner_id는 필수다. 다른 사람의 메일이 검색 대상에 들어갈 길을 만들지 않는다."""
        if not owner_id:
            raise ValueError("owner_id가 필요합니다")
        result = self.collection.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=k,
            where={"owner_id": owner_id},
        )
        return [
            Hit(_chunk(chunk_id, text, meta, owner_id), 1 - distance)
            for chunk_id, text, meta, distance in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]


def _meta(chunk: Chunk) -> dict:
    return {f.name: getattr(chunk, f.name) for f in fields(Chunk) if f.name not in ("id", "text")}


def _chunk(chunk_id: str, text: str, meta: dict, owner_id: str) -> Chunk:
    values = {key: value for key, value in meta.items() if key != "owner_id"}
    return Chunk(id=chunk_id.removeprefix(f"{owner_id}:"), text=text, **values)
