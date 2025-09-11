# src/core/providers/embeddings_provider.py
import os
import httpx
from typing import List

OPENROUTER_BASE = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api").rstrip("/")
EMBED_MODEL     = os.getenv("EMBED_MODEL", "text-embedding-3-small")
API_KEY         = os.getenv("LLM_API_KEY", "")

class EmbeddingsProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = (api_key or API_KEY).strip()
        self.base_url = (base_url or OPENROUTER_BASE).rstrip("/")
        self.model = (model or EMBED_MODEL).strip()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Gọi /v1/embeddings của OpenRouter.
        - Thêm header HTTP-Referer và X-Title theo khuyến nghị của OpenRouter.
        - Ném lỗi có nội dung dễ hiểu nếu status != 200.
        """
        url = f"{self.base_url}/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # 2 header giúp OpenRouter phân loại nguồn hợp lệ (tránh 401/rate-limit)
            "HTTP-Referer": "https://thienco-bot",
            "X-Title": "Thien Co Bot",
        }
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code != 200:
                # Ghi rõ body để dễ debug
                raise RuntimeError(f"Embeddings HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            return [item["embedding"] for item in data["data"]]
