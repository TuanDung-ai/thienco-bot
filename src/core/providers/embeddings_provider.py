# src/core/providers/embeddings_provider.py
import os
from functools import lru_cache
from sentence_transformers import SentenceTransformer

MODEL_ID = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

@lru_cache(maxsize=1)
def _load_model():
    # tải 1 lần, cache trong process
    return SentenceTransformer(MODEL_ID, device="cpu")  # Cloud Run dùng CPU

def embed(texts: list[str]) -> list[list[float]]:
    if not isinstance(texts, (list, tuple)):
        texts = [texts]
    model = _load_model()
    vecs = model.encode(list(texts), normalize_embeddings=True).tolist()
    return vecs

def embed_one(text: str) -> list[float]:
    return embed([text])[0]
