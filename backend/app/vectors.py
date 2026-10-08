from threading import RLock

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    def __init__(self, directory):
        self.lock = RLock()
        self.client = chromadb.PersistentClient(
            path=str(directory / "chroma"), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            "sira_openai_3_small_v1",
            embedding_function=None,
            metadata={"hnsw:space": "cosine", "embedding_model": "text-embedding-3-small", "dimensions": 1536},
        )

    def add(self, chunks, embeddings):
        with self.lock:
            self.collection.upsert(
                ids=[c["id"] for c in chunks],
                embeddings=embeddings,
                metadatas=[{"version_id": c["version_id"], "page": c["page"]} for c in chunks],
            )

    def delete(self, version_id):
        with self.lock:
            self.collection.delete(where={"version_id": version_id})

    def search(self, embedding, versions, limit=18):
        if not versions:
            return []
        with self.lock:
            count = self.collection.count()
            if not count:
                return []
            result = self.collection.query(
                query_embeddings=[embedding],
                where={"version_id": {"$in": versions}},
                n_results=min(limit, count),
                include=["distances"],
            )
        return list(zip(result["ids"][0], result["distances"][0]))
