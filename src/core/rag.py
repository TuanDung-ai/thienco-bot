# src/core/rag.py — Small-dimension (1536) RAG retriever for Thien Co Bot
import os, asyncio
from typing import List, Dict, Any
from supabase import Client

class RAGRetriever:
    def __init__(self, supabase_client: Client, embeddings_provider, dim: int = 384, topk: int = 8, min_score: float = 0.65):
        self.db = supabase_client
        self.emb = embeddings_provider
        self.dim = dim
        self.topk = topk
        self.min_score = min_score

    async def _retrieve_async(self, user_id: str, query_text: str) -> List[Dict[str, Any]]:
        # 1) Get embedding
        vecs = await self.emb.embed([query_text])
        q = vecs[0]

        # 2) Call RPC memory_search(u bigint, q vector(1536), k int)
        try:
            resp = self.db.rpc("memory_search", {"u": str(user_id), "q": q, "k": self.topk}).execute()
            rows = resp.data or []
        except Exception:
            rows = []

        # 3) Filter by score
        results = [r for r in rows if float(r.get("score", 0.0)) >= self.min_score]
        return results

    def retrieve_sync(self, user_id: int, query_text: str) -> List[Dict[str, Any]]:
        # Safe sync wrapper for Flask/gunicorn
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # If already in an event loop, the caller must be async; raise to avoid confusion.
            raise RuntimeError("retrieve_sync called inside a running event loop; use await _retrieve_async instead.")
        else:
            return asyncio.run(self._retrieve_async(user_id, query_text))

    @staticmethod
    def build_context(items: List[Dict[str, Any]], max_chars: int = 1200) -> str:
        # Join top items into a context block (truncated to max_chars).
        parts = []
        for i, it in enumerate(items, 1):
            score = float(it.get("score", 0.0))
            content = str(it.get("content", "")).strip()
            parts.append(f"[{i}] (score={score:.2f}) {content}")
        text = "\n".join(parts).strip()
        if len(text) > max_chars:
            return text[:max_chars] + " …"
        return text
