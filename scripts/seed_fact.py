# scripts/seed_fact.py — seed a durable fact and its embedding into Supabase
# Usage:
#   python -m scripts.seed_fact --user-id 123456 --content "Tên mình là Dũng, thích trà đá"
#   python -m scripts.seed_fact --user-id 123456 --content "..." --model openai/text-embedding-3-small
#   python -m scripts.seed_fact --user-id 123456 --content "..." --model sentence-transformers/all-MiniLM-L6-v2
#
# Requires env:
#   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
#   EMBED_MODEL (default sentence-transformers/all-MiniLM-L6-v2)
#   --- Chỉ khi dùng HTTP embeddings (OpenRouter/OpenAI) ---
#   LLM_BASE_URL (default https://openrouter.ai/api), LLM_API_KEY

import os, argparse, asyncio, json, sys, importlib.util
from typing import Optional, List

try:
    import httpx  # chỉ dùng khi gọi HTTP
except Exception:
    httpx = None


def env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None:
        return ""
    try:
        return v.encode("utf-8").decode("utf-8-sig").strip()
    except Exception:
        return str(v).strip()


SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
EMBED_MODEL  = env("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# HTTP embeddings (chỉ dùng khi provider = http)
BASE_URL = env("LLM_BASE_URL", "https://openrouter.ai/api").rstrip("/")
API_KEY  = env("LLM_API_KEY", "")


def embeddings_endpoint(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return f"{b}/embeddings"
    return f"{b}/v1/embeddings"


def is_local_model(model_id: str) -> bool:
    mid = (model_id or "").lower().strip()
    return mid.startswith("sentence-transformers/") or mid.startswith("local:")


# ---------- LOCAL provider (miễn phí) ----------
_local_model = None
def _load_local_model(model_id: str):
    global _local_model
    if _local_model is not None:
        return _local_model
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise SystemExit(
            "sentence-transformers chưa được cài. Thêm vào requirements.txt:\n"
            "  sentence-transformers>=3.0.0\n  torch>=2.1.0 (hoặc dùng FastEmbed nếu thiếu dung lượng)\n"
            f"Chi tiết lỗi import: {e}"
        )
    _local_model = SentenceTransformer(model_id, device="cpu")
    return _local_model


def get_embedding_local(text: str, model_id: str) -> List[float]:
    model = _load_local_model(model_id)
    vec = model.encode([text], normalize_embeddings=True)[0].tolist()
    return vec


# ---------- HTTP provider (OpenRouter/OpenAI) ----------
async def get_embedding_http(text: str, model_id: str, base_url: str, api_key: str) -> List[float]:
    if httpx is None:
        raise SystemExit("Thiếu httpx. Thêm vào requirements.txt: httpx>=0.27")
    url = embeddings_endpoint(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # 2 header dưới giúp OpenRouter không trả HTML
        "HTTP-Referer": "https://thienco.xyz",
        "X-Title": "Thien Co Bot",
        "User-Agent": "thienco-bot/1.0"
    }
    payload = {"model": model_id, "input": [text]}
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as c:
        r = await c.post(url, headers=headers, json=payload)
    ct = (r.headers.get("content-type") or "").lower()
    body_preview = r.text[:800]

    if "application/json" not in ct:
        raise SystemExit(
            f"[ERROR] HTTP embeddings không trả JSON (CT={ct}, status={r.status_code}).\n"
            f"URL: {url}\n"
            "→ Kiểm tra LLM_BASE_URL (/api), LLM_API_KEY và quyền model.\n"
            f"Body preview:\n{body_preview}"
        )

    data = r.json()
    if r.status_code != 200:
        raise SystemExit(f"[ERROR] {r.status_code}: {json.dumps(data)[:800]}")
    try:
        return data["data"][0]["embedding"]
    except Exception:
        raise SystemExit(f"[ERROR] JSON không có data[0].embedding:\n{json.dumps(data)[:800]}")


def pretty_dim_hint(dim: int) -> str:
    return (
        f"\nGỢI Ý: Cột 'embedding' trong Supabase phải là vector({dim})."
        "\nVí dụ SQL:\n"
        f"  alter table memory_vectors alter column embedding type vector({dim});\n"
        "  drop function if exists memory_search(bigint, vector, integer);\n"
        f"  create or replace function memory_search(u bigint, q vector({dim}), k int default 8)\n"
        "  returns table(ref_type text, ref_id text, content text, score float4)\n"
        "  language sql stable as $$\n"
        "    select ref_type, ref_id::text as ref_id, content, 1 - (embedding <=> q) as score\n"
        "    from memory_vectors\n"
        "    where user_id = u\n"
        "    order by embedding <=> q\n"
        "    limit k\n"
        "  $$;\n"
    )


def create_supabase_client():
    """
    Import an toàn để tránh bị 'shadow' bởi thư mục local tên 'supabase/' trong repo.
    """
    spec = importlib.util.find_spec("supabase")
    if spec is None or not spec.origin or "/site-packages/" not in spec.origin.replace("\\", "/"):
        raise SystemExit(
            "Không tìm thấy thư viện 'supabase' từ site-packages, hoặc đang bị đè bởi thư mục local.\n"
            "→ Cài đặt:  pip install -U 'supabase>=2.4.0'\n"
            "→ Nếu repo của bạn có thư mục tên 'supabase/', hãy đổi tên nó (vd: 'supabase_sql')."
        )
    from supabase import create_client  # type: ignore
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", type=int, required=True)
    ap.add_argument("--content", type=str, required=True)
    ap.add_argument("--model", type=str, default=EMBED_MODEL,
                    help="VD: sentence-transformers/all-MiniLM-L6-v2 (LOCAL) "
                         "hoặc openai/text-embedding-3-small (HTTP)")
    args = ap.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Thiếu SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")

    model_id = args.model.strip()

    # 1) Lấy embedding
    if is_local_model(model_id):
        if model_id.startswith("local:"):
            model_id = model_id.split("local:", 1)[1]
        emb = get_embedding_local(args.content, model_id)
        provider = "LOCAL"
    else:
        if not API_KEY:
            raise SystemExit("Thiếu LLM_API_KEY cho HTTP embeddings")
        if not BASE_URL:
            raise SystemExit("Thiếu LLM_BASE_URL cho HTTP embeddings")
        emb = asyncio.run(get_embedding_http(args.content, model_id, BASE_URL, API_KEY))
        provider = "HTTP"

    dim = len(emb)
    print(f"Provider: {provider} | Model: {model_id} | Embedding length: {dim}")

    # 2) Ghi vào Supabase
    db = create_supabase_client()
    fact = db.table("memory_facts").insert({
        "user_id": args.user_id,
        "content": args.content
    }).execute().data[0]
    fid = fact["id"]

    try:
        db.table("memory_vectors").insert({
            "user_id": args.user_id,
            "ref_type": "fact",
            "ref_id": fid,
            "content": args.content,
            "embedding": emb
        }).execute()
    except Exception as e:
        msg = str(e)
        if any(k in msg.lower() for k in ("expected", "dimension", "vector", "length", "size")):
            print("[ERROR] Lỗi khi insert vector vào Supabase (có thể sai số chiều).", file=sys.stderr)
            print(pretty_dim_hint(dim), file=sys.stderr)
        raise

    print(f"Inserted fact {fid} and its vector. Done.")


if __name__ == "__main__":
    main()
