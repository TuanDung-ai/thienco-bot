import os, sys, uuid, asyncio
from supabase import create_client
sys.path.insert(0, "src")
from core.providers.embeddings_provider import EmbeddingsProvider

USER = os.environ.get("USER_ID", "6149721828")
CONTENT = os.environ.get("FACT", "Tên mình là Dũng, thích trà đá")

async def main():
    sb  = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    emb = EmbeddingsProvider("", "", os.getenv("EMBED_MODEL","BAAI/bge-small-en-v1.5"))
    vec = (await emb.embed([CONTENT]))[0]
    try:
        r = sb.table("memory_facts").insert({"user_id": USER, "content": CONTENT, "meta": {}}).execute()
        fid = r.data[0]["id"]
    except Exception:
        fid = str(uuid.uuid4())
        sb.table("memory_facts").insert({"id": fid, "user_id": USER, "content": CONTENT, "meta": {}}).execute()
    sb.table("memory_vectors").insert({
        "user_id": USER, "ref_type": "fact", "ref_id": str(fid),
        "content": CONTENT, "embedding": vec
    }).execute()
    print("Seed OK. user:", USER, "fact_id:", fid, "dims:", len(vec))

asyncio.run(main())
