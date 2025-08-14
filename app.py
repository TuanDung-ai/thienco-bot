import os
import sys
import time
import logging
from collections import deque
import httpx
from flask import Flask, request, jsonify

# Add "src" to sys.path for absolute imports like "infra.*"
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("thienco-bot")

app = Flask(__name__)

# =====================
# PATCH: Env & runtime guards
# =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")

# Dedupe & rate-limit per chat
_seen = deque(maxlen=512)
_buckets = {}

def _allow(chat_id, limit=12, refill=12, window=60):
    now = int(time.time())
    q = _buckets.get(chat_id) or {"t": now, "tok": limit}
    elapsed = now - q["t"]
    if elapsed > 0:
        q["tok"] = min(limit, q["tok"] + int(elapsed * (refill / window)))
        q["t"] = now
    _buckets[chat_id] = q
    if q["tok"] > 0:
        q["tok"] -= 1
        return True
    return False

def _send_text(chat_id, text):
    if not TELEGRAM_TOKEN:
        logger.warning({"event": "missing_token"})
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=3.0, read=7.0, write=3.0)) as c:
            r = c.post(url, json=payload)
            logger.info({"event": "telegram_send", "status": r.status_code})
    except httpx.HTTPError:
        logger.exception("telegram_send_error")

@app.before_request
def _guard_webhook():
    # Chỉ áp dụng cho webhook POST
    if request.method != "POST":
        return None
    if request.path not in ("/telegram/webhook", "/"):
        return None

    # 1) Bắt buộc header secret để chặn scanner/spam
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_SECRET_TOKEN:
        return ("unauthorized", 401)

    # 2) Parse JSON nhẹ để kiểm tra tối thiểu + dedupe + rate-limit
    upd = request.get_json(silent=True) or {}
    upd_id = upd.get("update_id")
    msg = (upd.get("message") or upd.get("edited_message")) or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = msg.get("text")

    # Thiếu dữ liệu cơ bản thì bỏ qua (status 200 để Telegram không retry vô hạn)
    if not chat_id or not text:
        logger.info({"event": "skip_update", "reason": "no_chat_or_text", "update_id": upd_id})
        return jsonify({"ok": True}), 200

    # Dedupe theo update_id
    if upd_id in _seen:
        return jsonify({"ok": True}), 200
    _seen.append(upd_id)

    # Rate-limit nhẹ theo chat
    if not _allow(chat_id):
        _send_text(chat_id, "Nhiều tin nhắn quá 😅 đợi mình tí nhé…")
        return jsonify({"ok": True}), 200

    # Cho phép đi tiếp vào handler gốc
    return None

@app.get("/")
def root():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200

# Import sau khi setup sys.path
from functions.http.telegram_webhook import telegram_webhook_route  # noqa: E402

@app.post("/telegram/webhook")
def telegram_webhook():
    return telegram_webhook_route()

# Alias để Telegram có thể trỏ root path
@app.post("/")
def webhook_root_alias():
    return telegram_webhook_route()

# --- add below other routes in app.py ---
import datetime

@app.get("/version")
def version():
    rev = os.getenv("K_REVISION", "unknown")
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    return {"revision": rev, "built_at": ts}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
