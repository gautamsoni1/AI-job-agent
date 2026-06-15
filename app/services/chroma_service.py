from pathlib import Path

import chromadb
import structlog
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ChromaService:
    """Vector store service for semantic job-resume matching."""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self._ensure_collections()

    def _ensure_collections(self):
        self.resumes_collection = self.client.get_or_create_collection(
            name="resumes",
            metadata={"hnsw:space": "cosine"}
        )
        self.jobs_collection = self.client.get_or_create_collection(
            name="jobs",
            metadata={"hnsw:space": "cosine"}
        )

    def _embed(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    async def upsert_resume(self, user_id: str, resume_id: str, text: str, metadata: dict = None) -> bool:
        try:
            embedding = self._embed(text[:8000])
            self.resumes_collection.upsert(
                ids=[f"resume_{resume_id}"],
                embeddings=[embedding],
                documents=[text[:8000]],
                metadatas=[{"user_id": user_id, "resume_id": resume_id, **(metadata or {})}]
            )
            return True
        except Exception as e:
            logger.error("chroma_upsert_resume_failed", error=str(e))
            return False

    async def upsert_job(self, job_id: str, text: str, metadata: dict = None) -> bool:
        try:
            embedding = self._embed(text[:8000])
            self.jobs_collection.upsert(
                ids=[f"job_{job_id}"],
                embeddings=[embedding],
                documents=[text[:8000]],
                metadatas=[{"job_id": job_id, **(metadata or {})}]
            )
            return True
        except Exception as e:
            logger.error("chroma_upsert_job_failed", error=str(e))
            return False

    async def find_similar_jobs(self, resume_text: str, user_id: str, n_results: int = 20) -> list[dict]:
        try:
            embedding = self._embed(resume_text[:8000])
            results = self.jobs_collection.query(
                query_embeddings=[embedding],
                n_results=min(n_results, self.jobs_collection.count() or 1),
                include=["documents", "metadatas", "distances"]
            )
            jobs = []
            for i, job_id in enumerate(results["ids"][0]):
                jobs.append({
                    "job_id": results["metadatas"][0][i].get("job_id", ""),
                    "similarity_score": round((1 - results["distances"][0][i]) * 100, 2),
                    "metadata": results["metadatas"][0][i]
                })
            return jobs
        except Exception as e:
            logger.error("chroma_find_jobs_failed", error=str(e))
            return []

    async def compute_similarity(self, text1: str, text2: str) -> float:
        """Direct cosine similarity between two texts."""
        try:
            emb1 = self._embed(text1[:4000])
            emb2 = self._embed(text2[:4000])
            dot_product = sum(a * b for a, b in zip(emb1, emb2))
            return round(dot_product * 100, 2)
        except Exception as e:
            logger.error("chroma_similarity_failed", error=str(e))
            return 0.0

    async def delete_resume(self, resume_id: str) -> bool:
        try:
            self.resumes_collection.delete(ids=[f"resume_{resume_id}"])
            return True
        except Exception as e:
            logger.error("chroma_delete_resume_failed", error=str(e))
            return False