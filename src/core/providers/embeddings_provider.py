# src/core/providers/embeddings_provider.py
import os
from functools import lru_cache
from typing import Iterable, List

DEFAULT_MODEL = os.getenv("EMBED_MODEL", "local:BAAI/bge-small-en-v1.5")

@lru_cache(maxsize=1)
def _get_impl():
    """
    Trả về tuple (impl_name, impl_obj)
    impl_name: 'fastembed' | 'st'
    impl_obj: instance embedder tương ứng
    """
    model = os.getenv("EMBED_MODEL", DEFAULT_MODEL)

    # --- FastEmbed (khuyên dùng Cloud Run) ---
    if model.startswith("local:") or "bge-small" in model:
        # lazy import để giảm RAM lúc boot
        from fastembed import TextEmbedding
        return ("fastembed", TextEmbedding())

    # --- Sentence-Transformers (tùy chọn khi dev local) ---
    if model.startswith("sentence-transformers/"):
        from sentence_transformers import SentenceTransformer
        # luôn dùng CPU trên Cloud Run
        return ("st", SentenceTransformer(model, device="cpu"))

    raise RuntimeError(f"Unsupported EMBED_MODEL: {model}")

def _to_list(vec):
    return vec.tolist() if hasattr(vec, "tolist") else list(vec)

class EmbeddingsProvider:
    """
    API dùng thống nhất trong app:
      - EmbeddingsProvider.embed_one(text) -> List[float]
      - EmbeddingsProvider.embed_many(texts) -> List[List[float]]
    """

    @staticmethod
    def embed_many(texts: Iterable[str]) -> List[List[float]]:
        impl, emb = _get_impl()
        texts = list(texts or [])
        if not texts:
            return []
        if impl == "fastembed":
            # FastEmbed trả iterator -> list
            return [_to_list(v) for v in emb.embed(texts)]
        # Sentence-Transformers
        return [ _to_list(v) for v in emb.encode(texts, normalize_embeddings=True) ]

    @staticmethod
    def embed_one(text: str) -> List[float]:
        arr = EmbeddingsProvider.embed_many([text])
        return arr[0] if arr else []
