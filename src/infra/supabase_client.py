
from typing import Optional, Dict, Any
from .logging import log_error

_client = None

def init_supabase(url: Optional[str], key: Optional[str]):
    global _client
    if not url or not key:
        _client = None
        log_error("Supabase disabled (missing URL or SERVICE_ROLE_KEY).")
        return
    try:
        from supabase.client import create_client, Client
        _client = create_client(url, key)
    except Exception as e:
        _client = None
        log_error("Failed to init Supabase:", e)

def insert_message(row: Dict[str, Any]):
    if _client is None:
        return
    try:
        _client.table("messages").insert(row).execute()
    except Exception as e:
        log_error("Supabase insert error:", e)
