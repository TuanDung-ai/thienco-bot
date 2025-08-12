import json
import asyncio
import hashlib
from typing import Any, Dict

# Cloud Functions imports
from flask import Request, make_response

# ===== Import tuyệt đối (absolute imports) =====
from infra.config import load_settings_from_env
from infra.logging import log, log_error, Timer
from infra.telegram_api import send_message
from infra.supabase_client import init_supabase, insert_message
from core.llm_provider import ChatMessage, build_system_prompt
from core.providers.openrouter_provider import OpenRouterProvider

# ===== Singletons =====
SETTINGS = load_settings_from_env()

# ✅ Helper function (chỉ định nghĩa 1 lần)
def _mask(s: str) -> str:
    """Ẩn secret, chỉ hiển thị độ dài + 12 ký tự hash đầu"""
    if not s:
        return "len=0 sha256=none"
    return f"len={len(s)} sha256={hashlib.sha256(s.encode()).hexdigest()[:12]}"

# ✅ Debug LLM cấu hình (phát hiện lỗi thiếu biến)
log("LLM_CONFIG", {
    "LLM_API_KEY": _mask(SETTINGS.LLM_API_KEY),
    "LLM_MODEL": SETTINGS.LLM_MODEL,
    "LLM_BASE_URL": SETTINGS.LLM_BASE_URL,
})

if not SETTINGS.LLM_API_KEY:
    raise ValueError("❌ LLM_API_KEY is missing. Please cung cấp key LLM_API_KEY qua biến môi trường.")

init_supabase(SETTINGS.SUPABASE_URL, SETTINGS.SUPABASE_SERVICE_ROLE_KEY)
LLM = OpenRouterProvider(SETTINGS.LLM_API_KEY, SETTINGS.LLM_MODEL, SETTINGS.LLM_BASE_URL)

def _ok(body: Dict[str, Any] | str = "OK", code=200):
    if isinstance(body, str):
        body = {"ok": True, "message": body}
    resp = make_response(json.dumps(body, ensure_ascii=False), code)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

def _error(body: Dict[str, Any] | str, code=400):
    if isinstance(body, str):
        body = {"ok": False, "error": body}
    resp = make_response(json.dumps(body, ensure_ascii=False), code)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

async def _handle_update(update: Dict[str, Any]):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text") or ""

    # Commands
    if text.startswith("/"):
        cmd = text.split()[0].lower()

        if cmd == "/start":
            await send_message(
                SETTINGS.TELEGRAM_TOKEN,
                chat_id,
                "Xin chào, mình là Thiên Cơ. Gõ bất cứ điều gì để trò chuyện.\n"
                "• /help để xem hướng dẫn\n"
                "• /privacy để xem quyền riêng tư\n"
                "• /reset để xoá ngữ cảnh."
            )
            return

        if cmd == "/help":
            await send_message(
                SETTINGS.TELEGRAM_TOKEN,
                chat_id,
                "Mình có thể tóm tắt, viết lại, dàn ý, và trò chuyện về kế hoạch hàng ngày.\n"
                "Ví dụ: 'tóm tắt đoạn văn sau:' hoặc 'lập to-do cho buổi sáng'."
            )
            return

        if cmd == "/privacy":
            await send_message(
                SETTINGS.TELEGRAM_TOKEN,
                chat_id,
                "Quyền riêng tư: Hội thoại có thể được lưu tạm để cải thiện chất lượng. "
                "Dùng /reset để xoá ngữ cảnh. Bạn có thể yêu cầu xoá dữ liệu bất kỳ lúc nào."
            )
            return

        if cmd == "/reset":
            await send_message(
                SETTINGS.TELEGRAM_TOKEN,
                chat_id,
                "Đã xoá ngữ cảnh tạm thời (MVP chưa bật memory)."
            )
            return

    # Normal text -> call LLM
    try:
        system = build_system_prompt()
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=text),
        ]
        reply = await LLM.chat(
            messages,
            max_tokens=SETTINGS.MAX_TOKENS,
            temperature=SETTINGS.TEMPERATURE
        )

        await send_message(SETTINGS.TELEGRAM_TOKEN, chat_id, reply)

        # ✅ Sửa lỗi: sử dụng "user_id" thay vì "chat_id" để khớp với schema
        if chat_id:
            insert_message({
                "user_id": chat_id,  # ✅ Khớp với schema Supabase
                "role": "user",
                "content": text,
            })
            insert_message({
                "user_id": chat_id,  # ✅ Khớp với schema Supabase
                "role": "assistant",
                "content": reply,
            })
    except Exception as e:
        log_error("Error processing message:", str(e))
        # Gửi thông báo lỗi cho user
        try:
            await send_message(
                SETTINGS.TELEGRAM_TOKEN, 
                chat_id, 
                "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau."
            )
        except:
            pass  # Tránh lỗi chồng lỗi

def telegram_webhook(request: Request):
    # Verify secret header với debug
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    expected = SETTINGS.TELEGRAM_SECRET_TOKEN.strip()

    log("startup expected_secret", _mask(expected))
    log("request header_secret", _mask(secret))

    if secret != expected:
        return _error("Unauthorized: bad secret header", 401)

    try:
        update = request.get_json(force=True, silent=False)
        if not update:
            return _error("Empty request body", 400)
    except Exception as e:
        log_error("Bad JSON:", e)
        return _error("Bad request JSON", 400)

    # Run async handler
    try:
        timer = Timer()
        asyncio.run(_handle_update(update))
        ms = timer.stop_ms()
        log("handled update in", ms, "ms")
        return _ok({"handled_ms": ms})
    except Exception as e:
        log_error("handler error:", e)
        return _error("Internal error", 500)
