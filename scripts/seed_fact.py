# scripts/seed_fact.py — seed a durable fact and its embedding into Supabase
# Usage:
#   python scripts/seed_fact.py --user-id 123456 --content "Tên mình là Dũng, thích trà đá" [--model openai/text-embedding-3-small]
#
# Requires env:
#   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
#   LLM_BASE_URL (default https://openrouter.ai/api), LLM_API_KEY
#   EMBED_MODEL (default openai/text-embedding-3-small)
import os, argparse, asyncio
from supabase import create_client
from typing import Optional
from httpx import AsyncClient

def env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None: return ""
    try:
        return v.encode("utf-8").decode("utf-8-sig").strip()
    except Exception:
        return v.strip()

SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
BASE_URL     = env("LLM_BASE_URL", "https://openrouter.ai/api").rstrip("/")
API_KEY      = env("LLM_API_KEY", "")
EMBED_MODEL  = env("EMBED_MODEL", "openai/text-embedding-3-small")

def embeddings_endpoint(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/embeddings"
    return f"{b}/v1/embeddings"

async def get_embedding(text: str, model: str) -> list[float]:
    url = embeddings_endpoint(BASE_URL)
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "HTTP-Referer": "https://thienco.xyz",
        "X-Title": "Thien Co Bot",
        "User-Agent": "thienco-bot/1.0"
    }
    async with AsyncClient(timeout=60.0) as c:
        r = await c.post(url, json={"model": model, "input": [text]}, headers=headers)
        ct = r.headers.get("content-type", "")
        if r.status_code != 200 or "application/json" not in ct:
            raise SystemExit(f"[ERROR] {r.status_code} CT={ct}\n{r.text[:500]}")
        data = r.json()
        return data["data"][0]["embedding"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", type=int, required=True)
    ap.add_argument("--content", type=str, required=True)
    ap.add_argument("--model", type=str, default=EMBED_MODEL)
    args = ap.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
    if not API_KEY:
        raise SystemExit("Missing LLM_API_KEY")
    if not BASE_URL:
        raise SystemExit("Missing LLM_BASE_URL")

    # 1) Get embedding
    emb = asyncio.run(get_embedding(args.content, args.model))
    print(f"Embedding length: {len(emb)}")

    # 2) Insert into Supabase
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    fact = db.table("memory_facts").insert({"user_id": args.user_id, "content": args.content}).execute().data[0]
    fid = fact["id"]
    vec = {
        "user_id": args.user_id,
        "ref_type": "fact",
        "ref_id": fid,
        "content": args.content,
        "embedding": emb
    }
    db.table("memory_vectors").insert(vec).execute()
    print(f"Inserted fact {fid} and its vector. Done.")

if __name__ == "__main__":
    main()
