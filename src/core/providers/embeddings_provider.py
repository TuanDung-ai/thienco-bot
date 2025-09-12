# src/core/providers/embeddings_provider.py
import os
from functools import lru_cache
from typing import List

DEFAULT_MODEL = os.getenv("EMBED_MODEL", "local:BAAI/bge-small-en-v1.5")

@lru_cache(maxsize=1)
def _get_embedder():
    model = os.getenv("EMBED_MODEL", DEFAULT_MODEL)

    # FastEmbed (khuyên dùng trên Cloud Run)
    if model.startswith("local:") or "bge-small" in model:
        from fastembed import TextEmbedding  # lazy import
        return ("fastembed", TextEmbedding())  # 384d

    # (Tùy chọn) Sentence-Transformers cho môi trường cục bộ
    if model.startswith("sentence-transformers/"):
        from sentence_transformers import SentenceTransformer  # lazy import
        return ("st", SentenceTransformer(model, device="cpu"))

    raise RuntimeError(f"Unsupported EMBED_MODEL: {model}")

def embed(texts: List[str]) -> List[List[float]]:
    impl, emb = _get_embedder()
    if impl == "fastembed":
        return [vec.tolist() if hasattr(vec, "tolist") else list(vec)
                for vec in emb.embed(texts)]
    # impl == "st"
    return [emb.encode(t, normalize_embeddings=True).tolist() for t in texts]
