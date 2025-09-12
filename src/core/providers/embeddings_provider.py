# src/core/providers/embeddings_provider.py
import os
from functools import lru_cache
from typing import Iterable, List

DEFAULT_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
CACHE_DIR = os.getenv("FASTEMBED_CACHE_DIR", "/tmp/fastembed")

@lru_cache(maxsize=1)
def _get_fastembed(model_id: str):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=model_id, cache_dir=CACHE_DIR)

def _to_pyfloat_list(vec) -> List[float]:
    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    return [float(x) for x in vec]

class EmbeddingsProvider:
    def __init__(self, api_key: str = "", base_url: str = "", model_id: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.model_id = model_id or DEFAULT_MODEL

    async def embed(self, texts: Iterable[str]) -> List[List[float]]:
        texts = list(texts or [])
        if not texts:
            return []
        emb = _get_fastembed(self.model_id)
        return [_to_pyfloat_list(v) for v in emb.embed(texts)]
