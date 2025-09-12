# src/core/memory_store.py
import os
from typing import List, Dict, Any
from supabase import create_client
from core.providers.embeddings_provider import EmbeddingsProvider

EMBED_MODEL   = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
BASE_URL      = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api")
API_KEY       = os.getenv("LLM_API_KEY", "")
SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TOPK          = int(os.getenv("MEMORY_TOPK", "8"))

class MemoryStore:
    def __init__(self):
        self.db = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None
        self.emb = EmbeddingsProvider(API_KEY, BASE_URL, EMBED_MODEL)

    async def search(self, user_id: int | str, query: str, top_k: int = TOPK) -> List[Dict[str, Any]]:
        if not self.db:
            return []
        vec = (await self.emb.embed([query]))[0]
        # user_id dạng TEXT trong DB hiện tại → ép string cho an toàn
        rpc = self.db.rpc("memory_search", {"u": str(user_id), "q": vec, "k": top_k}).execute()
        return rpc.data or []

    async def add_fact(self, user_id: int | str, content: str, weight: float = 1.0):
        if not self.db:
            return
        res = self.db.table("memory_facts").insert({
            "user_id": str(user_id),
            "content": content,
            "meta": {"weight": weight}
        }).execute()
        fid = res.data[0]["id"]
        emb = (await self.emb.embed([content]))[0]
        self.db.table("memory_vectors").insert({
            "user_id": str(user_id),
            "ref_type": "fact",
            "ref_id": fid,
            "content": content,
            "embedding": emb
        }).execute()

    async def add_summary(self, user_id: int | str, window_start_at: str, window_end_at: str, summary: str):
        if not self.db:
            return
        res = self.db.table("conv_summaries").insert({
            "user_id": str(user_id),
            "window_start_at": window_start_at,
            "window_end_at": window_end_at,
            "summary": summary
        }).execute()
        sid = res.data[0]["id"]
        emb = (await self.emb.embed([summary]))[0]
        self.db.table("memory_vectors").insert({
            "user_id": str(user_id),
            "ref_type": "summary",
            "ref_id": sid,              # <— dùng ref_id, KHÔNG phải summary_id
            "content": summary,
            "embedding": emb
        }).execute()
