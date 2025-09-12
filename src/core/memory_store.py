import os, asyncio
from typing import List, Dict, Any
from supabase.client import create_client
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

    async def search(self, user_id: int, query: str, top_k: int = TOPK) -> List[Dict[str, Any]]:
        if not self.db:
            return []
        vec = (await self.emb.embed([query]))[0]
        rpc = self.db.rpc("memory_search", {"u": user_id, "q": vec, "k": top_k}).execute()
        return rpc.data or []

    async def add_fact(self, user_id: int, content: str, weight: float = 1.0):
        if not self.db: return
        res = self.db.table("memory_facts").insert({"user_id": user_id, "content": content, "weight": weight}).execute()
        fid = res.data[0]["id"]
        emb = (await self.emb.embed([content]))[0]
        self.db.table("memory_vectors").insert({
            "user_id": user_id, "ref_type": "summary", "ref_id": sid, "content": summary, "embedding": emb
        }).execute()

    async def add_summary(self, user_id: int, window_start_at: str, window_end_at: str, summary: str):
        if not self.db: return
        res = self.db.table("conv_summaries").insert({
            "user_id": user_id, "window_start_at": window_start_at, "window_end_at": window_end_at, "summary": summary
        }).execute()
        sid = res.data[0]["id"]
        emb = (await self.emb.embed([summary]))[0]
        self.db.table("memory_vectors").insert({
            "user_id": user_id, "ref_type": "summary", "ref_id": sid, "content": summary, "embedding": emb
        }).execute()
