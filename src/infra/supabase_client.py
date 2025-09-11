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
    Ghi vào public.messages.
    - Bảng hiện tại của bạn còn ràng buộc NOT NULL cho cột chat_id.
      Do đó ta điền CẢ `chat_id` và `user_id` = cùng giá trị (Telegram chat_id).
    - Chấp nhận đầu vào có 'user_id' hoặc 'chat_id'.
    """
    if _client is None:
        return
    try:
        uid = row.get("user_id") or row.get("chat_id")
        if not uid:
            log_error("Supabase insert skipped: missing user_id/chat_id.")
            return
        payload = {
            "user_id": uid,
            "chat_id": uid,                 # <-- QUAN TRỌNG để thỏa NOT NULL chat_id
            "role": row.get("role", "user"),
            "content": row.get("content", ""),
        }
        _client.table("messages").insert(payload).execute()
    except Exception as e:
        log_error(f"Supabase insert error: {e}")
