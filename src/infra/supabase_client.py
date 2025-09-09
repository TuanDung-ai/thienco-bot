# src/infra/supabase_client.py
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
    """
    Hỗ trợ cả 'chat_id' (Telegram) lẫn 'user_id' (schema).
    Luôn insert vào cột 'user_id' của bảng messages.
    """
    if _client is None:
        return
    user_id = row.get("user_id") or row.get("chat_id")
    if not user_id:
        log_error("Supabase insert skipped: user_id/chat_id missing.")
        return
    payload = {
        "user_id": user_id,
        "role": row.get("role", "user"),
        "content": row.get("content", ""),
    }
    # created_at do DB tự set; nếu muốn custom thì thêm payload["created_at"].
    try:
        _client.table("messages").insert(payload).execute()
    except Exception as e:
        log_error("Supabase insert error:", e)
