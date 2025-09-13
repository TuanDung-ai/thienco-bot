# src/infra/supabase_client.py
from typing import Optional, Dict, Any
from .logging import log_error

_client = None

def init_supabase(url: Optional[str], key: Optional[str]) -> None:
    """
    Khởi tạo client toàn cục. Không raise để tránh làm vỡ webhook.
    """
    global _client
    if not url or not key:
        _client = None
        log_error("Supabase disabled: missing URL or SERVICE_ROLE_KEY.")
        return
    try:
        # supabase >= 2.x
        from supabase import create_client, Client  # type: ignore
        _client = create_client(url, key)  # type: ignore[assignment]
    except Exception as e:
        _client = None
        log_error(f"Supabase init error: {e}")

def is_ready() -> bool:
    return _client is not None

def insert_message(row: Dict[str, Any]) -> None:
    """
    Ghi vào public.messages (resilient):
    - Ưu tiên insert có 'chat_id' (nếu bảng có cột này).
    - Nếu lỗi vì thiếu cột chat_id -> fallback insert không chat_id.
    """
    if _client is None:
        return
    try:
        uid = row.get("user_id") or row.get("chat_id")
        if not uid:
            log_error("Supabase insert skipped: missing user_id/chat_id.")
            return

        base_payload = {
            "user_id": uid,
            "role": row.get("role", "user"),
            "content": row.get("content", ""),
        }

        # 1) thử với chat_id
        try:
            payload_with_chat = {**base_payload, "chat_id": uid}
            _client.table("messages").insert(payload_with_chat).execute()
            return
        except Exception as e1:
            msg = str(e1).lower()
            if "chat_id" not in msg and "column" not in msg:
                # lỗi khác, log rồi thử fallback
                log_error(f"messages insert (with chat_id) error: {e1}")

        # 2) fallback: không chat_id
        _client.table("messages").insert(base_payload).execute()

    except Exception as e:
        log_error(f"Supabase insert error: {e}")
