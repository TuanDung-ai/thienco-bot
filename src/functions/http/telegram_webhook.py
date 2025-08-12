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

def _ok(body: Dict[str, Any] | None = None, status: int = 200):
    resp = make_response(json.dumps(body or {"ok": True}), status)
    resp.headers["Content-Type"] = "application/json"
    return resp

def _error(message: str, status: int = 400):
    return _ok({"ok": False, "error": message}, status)

def _verify_secret(req: Request, secret_expected: str | None) -> bool:
    if not secret_expected:
        # If no secret configured, accept all (not recommended for prod)
        return True
    got = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    # constant-time compare
    return hashlib.sha256(got.encode()).hexdigest() == hashlib.sha256(secret_expected.encode()).hexdigest()

async def _handle_update(update: Dict[str, Any]):
    settings = load_settings_from_env()
    init_supabase(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        log("no message in update")
        return

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    # Log to Supabase (best-effort)
    insert_message({"user_id": chat_id, "role": "user", "content": text})

    # If no API key, simple ping/pong fallback
    if not settings.LLM_API_KEY:
        reply = "Bot đang chạy (no LLM_API_KEY). Bạn gửi: " + (text or "(empty)")
        await send_message(settings.TELEGRAM_TOKEN, chat_id, reply)
        insert_message({"user_id": chat_id, "role": "assistant", "content": reply})
        return

    provider = OpenRouterProvider(settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_BASE_URL)
    messages = [
        ChatMessage(role="system", content=build_system_prompt()),
        ChatMessage(role="user", content=text or "ping"),
    ]
    try:
        answer = await provider.chat(messages, max_tokens=settings.MAX_TOKENS, temperature=settings.TEMPERATURE)
    except Exception as e:
        log_error("LLM error:", e)
        answer = "Xin lỗi, LLM đang lỗi. Thử lại sau nhé."

    # Send and log
    await send_message(settings.TELEGRAM_TOKEN, chat_id, answer, parse_mode="Markdown")
    insert_message({"user_id": chat_id, "role": "assistant", "content": answer})

def telegram_webhook_route():
    settings = load_settings_from_env()

    if not _verify_secret(request, settings.TELEGRAM_SECRET_TOKEN):
        log_error("Invalid secret token")
        return _error("Unauthorized", 401)

    try:
        update = request.get_json(force=True, silent=False)
        if not isinstance(update, dict):
            raise ValueError("JSON is not an object")
    except Exception as e:
        log_error("Bad JSON:", e)
        return _error("Bad request JSON", 400)

    try:
        timer = Timer()
        asyncio.run(_handle_update(update))
        ms = timer.stop_ms()
        log("handled update in", ms, "ms")
        return _ok({"handled_ms": ms})
    except Exception as e:
        log_error("handler error:", e)
        return _error("Internal error", 500)
