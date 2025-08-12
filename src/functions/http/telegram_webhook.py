import json
import asyncio
import hashlib
from typing import Any, Dict

from flask import Request, request, make_response

from infra.config import load_settings_from_env
from infra.logging import log, log_error, Timer
from infra.telegram_api import send_message
from infra.supabase_client import init_supabase, insert_message
from core.llm_provider import ChatMessage, build_system_prompt
from core.providers.openrouter_provider import OpenRouterProvider

# =====================
# Helpers: HTTP responses
# =====================

def _ok(body: Dict[str, Any] | None = None, status: int = 200):
    resp = make_response(json.dumps(body or {"ok": True}), status)
    resp.headers["Content-Type"] = "application/json"
    return resp


def _error(message: str, status: int = 400):
    return _ok({"ok": False, "error": message}, status)


# =====================
# Security: constant-time secret verify (defense-in-depth)
# =====================

def _verify_secret(req: Request, secret_expected: str | None) -> bool:
    if not secret_expected:
        # Nếu chưa cấu hình secret, tạm chấp nhận (không khuyến nghị production)
        return True
    got = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hashlib.sha256(got.encode()).hexdigest() == hashlib.sha256(secret_expected.encode()).hexdigest()


# =====================
# Core handler (async)
# =====================

async def _safe_insert_message(data: Dict[str, Any]):
    try:
        insert_message(data)
    except Exception as e:
        log_error("supabase insert error:", e)


async def _send_safe(token: str, chat_id: int, text: str, parse_mode: str | None = "Markdown"):
    """Gửi Telegram an toàn: nếu lỗi parse Markdown, thử lại dạng thường."""
    try:
        await send_message(token, chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        log_error("telegram send error (markdown):", e)
        try:
            await send_message(token, chat_id, text, parse_mode=None)
        except Exception as e2:
            log_error("telegram send error (plain):", e2)


async def _handle_update(update: Dict[str, Any]):
    settings = load_settings_from_env()

    # Chuẩn bị Supabase (best-effort)
    try:
        init_supabase(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    except Exception as e:
        log_error("supabase init error:", e)

    # Parse message
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        log("no message in update")
        return

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if not chat_id:
        log("missing chat_id; skip")
        return

    # Cắt input để tiết kiệm chi phí
    max_input = getattr(settings, "MAX_INPUT", 1000)
    user_text = (text or "").strip()[: max(1, int(max_input))]

    # Ghi log người dùng (best‑effort, không chặn luồng)
    await _safe_insert_message({"user_id": chat_id, "role": "user", "content": user_text})

    # Trường hợp không có API key → trả lời nhanh để xác nhận bot sống
    if not getattr(settings, "LLM_API_KEY", None):
        reply = "Bot đang chạy (no LLM_API_KEY). Bạn gửi: " + (user_text or "(empty)")
        await _send_safe(settings.TELEGRAM_TOKEN, chat_id, reply)
        await _safe_insert_message({"user_id": chat_id, "role": "assistant", "content": reply})
        return

    # Fast‑path cho lệnh cơ bản (giảm gọi LLM)
    low = user_text.lower()
    if low in ("/start", "start", "hi", "hello"):
        reply = (
            "Xin chào, mình là Thiên Cơ 🤖. Cứ nhắn tin là mình trợ giúp ngay!\n"
            "(Mẹo: cứ hỏi ngắn gọn để phản hồi nhanh và tiết kiệm chi phí)"
        )
        await _send_safe(settings.TELEGRAM_TOKEN, chat_id, reply)
        await _safe_insert_message({"user_id": chat_id, "role": "assistant", "content": reply})
        return

    # Chuẩn bị lời gọi LLM
    provider = OpenRouterProvider(settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_BASE_URL)
    messages = [
        ChatMessage(role="system", content=build_system_prompt()),
        ChatMessage(role="user", content=user_text or "ping"),
    ]

    # Gọi LLM với retry + timeout (asyncio.wait_for)
    llm_timeout = int(getattr(settings, "LLM_TIMEOUT", 8))  # giây
    max_tokens = int(getattr(settings, "MAX_TOKENS", 256))
    temperature = float(getattr(settings, "TEMPERATURE", 0.3))

    answer: str | None = None
   for i in range(3):
    try:
        t = Timer()  # không truyền label
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
        except asyncio.TimeoutError:
            log_error(f"LLM timeout at retry {i}")
            await asyncio.sleep(0.4 * (2 ** i))
        except Exception as e:
            log_error("LLM error:", e)
            await asyncio.sleep(0.4 * (2 ** i))

    if not answer:
        answer = "Xin lỗi, hệ thống đang bận. Mình trả lời ngắn trước nhé 🤖💤"

    # Gửi và log (best‑effort)
    await _send_safe(settings.TELEGRAM_TOKEN, chat_id, answer, parse_mode="Markdown")
    await _safe_insert_message({"user_id": chat_id, "role": "assistant", "content": answer})


# =====================
# Flask entrypoint
# =====================

def telegram_webhook_route():
    settings = load_settings_from_env()

    # Defense‑in‑depth: verify secret ở đây nữa (đã có lớp ở app.py)
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
