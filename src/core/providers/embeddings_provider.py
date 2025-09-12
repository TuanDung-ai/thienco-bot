import os
from functools import lru_cache
from typing import List
from fastembed import TextEmbedding

MODEL_ID = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")  # dim=384

@lru_cache(maxsize=1)
def _embedder():
    # download 1 lần, chạy CPU
    return TextEmbedding(model_name=MODEL_ID, cache_dir="/tmp/fastembed")

def embed(texts: List[str]) -> List[List[float]]:
    if not isinstance(texts, (list, tuple)):
        texts = [texts]
    emb = list(_embedder().embed(texts))
    # normalize = False theo mặc định; nếu cần cosine, có thể tự chuẩn hóa
    return [list(v) for v in emb]

def embed_one(text: str) -> List[float]:
    return embed([text])[0]
