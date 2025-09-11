# src/core/providers/embeddings_provider.py — robust OpenRouter embeddings client
import os
import httpx
from typing import List

def _clean(s: str | None) -> str:
    if s is None: return ""
    try:
        return s.encode("utf-8").decode("utf-8-sig").strip()
    except Exception:
        return s.strip()

OPENROUTER_BASE = _clean(os.getenv("LLM_BASE_URL", "https://openrouter.ai/api")).rstrip("/")
API_KEY         = _clean(os.getenv("LLM_API_KEY", ""))
EMBED_MODEL     = _clean(os.getenv("EMBED_MODEL", "openai/text-embedding-3-small"))

def _ensure_openrouter_embedding_id(model: str) -> str:
    # If the user passes 'text-embedding-3-small', prepend 'openai/' for OpenRouter
    if model and "/" not in model and "openrouter.ai" in OPENROUTER_BASE:
        return "openai/" + model
    return model

def _embeddings_endpoint(base: str) -> str:
    # Accept both ".../api" and ".../api/v1"
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/embeddings"
    return f"{b}/v1/embeddings"

class EmbeddingsProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, timeout: float = 60.0):
        self.api_key  = _clean(api_key or API_KEY)
        self.base_url = _clean(base_url or OPENROUTER_BASE).rstrip("/")
        self.model    = _ensure_openrouter_embedding_id(_clean(model or EMBED_MODEL))
        self.timeout  = timeout

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError("Missing LLM_API_KEY")
        if not self.base_url:
            raise RuntimeError("Missing LLM_BASE_URL")
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise TypeError("texts must be List[str]")

        url = _embeddings_endpoint(self.base_url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # These two help OpenRouter attribute usage for free-tier keys
            "HTTP-Referer": "https://thienco.xyz",
            "X-Title": "Thien Co Bot",
            "User-Agent": "thienco-bot/1.0 (+https://thienco.xyz)"
        }
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload, headers=headers)
            ct = r.headers.get("content-type", "")
            if r.status_code != 200:
                snippet = r.text[:400]
                raise RuntimeError(f"Embeddings HTTP {r.status_code} (CT={ct}). Body: {snippet}")
            if "application/json" not in ct:
                snippet = r.text[:400]
                raise RuntimeError(f"Embeddings content-type not JSON (CT={ct}). Body: {snippet}")
            data = r.json()
            try:
                return [item["embedding"] for item in data["data"]]
            except Exception as e:
                raise RuntimeError(f"Unexpected embeddings payload: {data}") from e
