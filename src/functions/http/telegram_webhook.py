import json
import asyncio
import hmac
from typing import Any, Dict, Optional

from flask import Request, request, make_response

from infra.config import load_settings_from_env
from infra.logging import log, log_error, Timer
from infra.telegram_api import send_message
from infra.supabase_client import init_supabase, insert_message
from core.llm_provider import ChatMessage, build_system_prompt
from core.providers.openrouter_provider import OpenRouterProvider

from infra.telegram_api import send_message, send_typing  # add import

async def _handle_update(update: Dict[str, Any]):
    settings = load_settings_from_env()
    _init_supabase_if_configured(settings)

    # --- gửi typing sớm ---
    chat_id = ((update.get("message") or update.get("edited_message")) or {}).get("chat", {}).get("id")
    if chat_id:
        try:
            await send_typing(settings.TELEGRAM_TOKEN, chat_id)
        except Exception as e:
            log_error("typing warn:", e)


# =====================
# HTTP helpers
# =====================

def _ok(body: Optional[Dict[str, Any]] = None, status: int = 200):
    resp = make_response(json.dumps(body or {"ok": True}), status)
    resp.headers["Content-Type"] = "application/json"
    return resp


def _error(message: str, status: int = 400):
    return _ok({"ok": False, "error": message}, status)


# =====================
# Security
# =====================

def _verify_secret(req: Request, secret_expected: Optional[str]) -> bool:
    """Verify Telegram secret header (defense-in-depth)."""
    if not secret_expected:
        # Không khuyến nghị cho production, nhưng không chặn nếu chưa cấu hình.
        return True
    got = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    # So sánh constant-time
    return hmac.compare_digest(got, secret_expected)


# =====================
# Supabase helpers (no-op nếu chưa cấu hình)
# =====================

def _supabase_is_configured(settings) -> bool:
    return bool(getattr(settings, "SUPABASE_URL", "") and getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", ""))


def _init_supabase_if_configured(settings) -> None:
    if _supabase_is_configured(settings):
        try:
            init_supabase(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        except Exception as e:
            # Không làm vỡ luồng nếu key sai; chỉ log nhẹ.
            log_error("supabase init error:", e)


async def _safe_insert_message(settings, data: Dict[str, Any]) -> None:
    if not _supabase_is_configured(settings):
        return
    try:
        insert_message(data)
    except Exception as e:
        # Best-effort: không để lỗi DB ảnh hưởng webhook
        log_error("supabase insert error:", e)


# =====================
# Telegram helper (safe send)
# =====================

async def _send_safe(token: str, chat_id: int, text: str, parse_mode: Optional[str] = "Markdown") -> None:
    """Gửi Telegram an toàn: nếu lỗi Markdown, thử lại dạng thường."""
    try:
        await send_message(token, chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        log_error("telegram send error (markdown):", e)
        try:
            await send_message(token, chat_id, text, parse_mode=None)
        except Exception as e2:
            log_error("telegram send error (plain):", e2)


# =====================
# Core handler (async)
# =====================

async def _handle_update(update: Dict[str, Any]):
    settings = load_settings_from_env()

    # Supabase (chỉ init nếu có cấu hình đầy đủ)
    _init_supabase_if_configured(settings)

    # Parse message
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        log("no message in update")
        return

    chat = (msg.get("chat") or {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if not chat_id:
        log("missing chat_id; skip")
        return

    # Cắt input để tiết kiệm chi phí
    max_input = int(getattr(settings, "MAX_INPUT", 1000))
    user_text = (text or "").strip()[: max(1, max_input)]

    # Ghi log người dùng (best-effort, no-op nếu Supabase chưa cấu hình)
    await _safe_insert_message(settings, {"user_id": chat_id, "chat_id": chat_id, "role": "user", "content": user_text})

    # Thiếu API key → trả lời xác nhận bot đang sống
    if not getattr(settings, "LLM_API_KEY", None):
        reply = "Bot đang chạy (no LLM_API_KEY). Bạn gửi: " + (user_text or "(empty)")
        await _send_safe(settings.TELEGRAM_TOKEN, chat_id, reply)
        await _safe_insert_message(settings, {"user_id": chat_id, "chat_id": chat_id, "role": "assistant", "content": reply})
        return

    # Fast-path cho lệnh cơ bản (giảm gọi LLM)
    low = user_text.lower()
    if low in ("/start", "start", "hi", "hello", "/help"):
        reply = (
            "Xin chào, mình là Thiên Cơ 🤖. Cứ nhắn tin là mình trợ giúp ngay!\n"
            "(Mẹo: hỏi ngắn gọn để phản hồi nhanh & tiết kiệm chi phí)\n"
            "Lệnh nhanh: /help – hướng dẫn | /start – bắt đầu"
        )
        await _send_safe(settings.TELEGRAM_TOKEN, chat_id, reply)
        await _safe_insert_message(settings, {"user_id": chat_id, "chat_id": chat_id, "role": "assistant", "content": reply})
        return

    # Chuẩn bị lời gọi LLM
    provider = OpenRouterProvider(settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_BASE_URL)
    messages = [
        ChatMessage(role="system", content=build_system_prompt()),
        ChatMessage(role="user", content=user_text or "ping"),
    ]

    # Gọi LLM với retry + timeout
    llm_timeout = int(getattr(settings, "LLM_TIMEOUT", 8))  # giây
    max_tokens = int(getattr(settings, "MAX_TOKENS", 256))
    temperature = float(getattr(settings, "TEMPERATURE", 0.3))

    answer: Optional[str] = None
    for i in range(3):
        try:
            t = Timer()  # KHÔNG truyền tham số cho Timer
            answer = await asyncio.wait_for(
                provider.chat(messages, max_tokens=max_tokens, temperature=temperature),
                timeout=llm_timeout,
            )
            ms = t.stop_ms()
            log("llm_call_retry", i, "ms", ms)
            break
        except asyncio.TimeoutError:
            log_error(f"LLM timeout at retry {i}")
            await asyncio.sleep(0.4 * (2 ** i))
        except Exception as e:
            log_error("LLM error:", e)
            await asyncio.sleep(0.4 * (2 ** i))

    if not answer:
        answer = "Xin lỗi, hệ thống đang bận. Mình trả lời ngắn trước nhé 🤖💤"

    # Gửi và log (best-effort)
    await _send_safe(settings.TELEGRAM_TOKEN, chat_id, answer, parse_mode="Markdown")
    await _safe_insert_message(settings, {"user_id": chat_id, "chat_id": chat_id, "role": "assistant", "content": answer})


# =====================
# Flask entrypoint
# =====================

def telegram_webhook_route():
    settings = load_settings_from_env()

    # Verify secret lần nữa (đã có lớp ở app.py)
    if not _verify_secret(request, settings.TELEGRAM_SECRET_TOKEN):
        log_error("Invalid secret token")
        return _error("Unauthorized", 401)

    # Parse JSON an toàn
    try:
        update = request.get_json(force=True, silent=False)
        if not isinstance(update, dict):
            raise ValueError("JSON is not an object")
    except Exception as e:
        log_error("Bad JSON:", e)
        return _error("Bad request JSON", 400)

    # Xử lý cập nhật
    try:
        timer = Timer()
        asyncio.run(_handle_update(update))
        ms = timer.stop_ms()
        log("handled update in", ms, "ms")
        return _ok({"handled_ms": ms})
    except Exception as e:
        log_error("handler error:", e)
        return _error("Internal error", 500)
