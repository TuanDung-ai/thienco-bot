import os
import sys
import time
import logging
from collections import deque

import httpx
from flask import Flask, request, jsonify

# ============ Path setup ============
# Add "src" to sys.path for absolute imports like "infra.*" / "functions.*"
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ============ Logging ============
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # giảm noise httpx
logger = logging.getLogger("thienco-bot")

# ============ Flask App ============
app = Flask(__name__)

# ============ Env & runtime guards ============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")

# Dedupe update_id & rate-limit đơn giản theo chat
_seen = deque(maxlen=512)
_buckets = {}  # chat_id -> {t: last_ts, tok: tokens}


def _allow(chat_id, limit=12, refill=12, window=60):
    """Token bucket đơn giản: limit token / window giây (refill đều)."""
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
    """Gửi tin nhắn Telegram ngắn gọn để báo trạng thái (rate-limit…)."""
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


def _is_json_request(req):
    """Chỉ chấp nhận JSON cho webhook POST để tránh rác/scanner."""
    ct = (req.headers.get("Content-Type") or "").lower()
    return ct.startswith("application/json")


@app.before_request
def _guard_webhook():
    """
    Lớp bảo vệ nhẹ cho webhook:
      - Yêu cầu header secret
      - Bắt buộc Content-Type JSON
      - Dedupe update_id
      - Rate-limit theo chat
    """
    if request.method != "POST":
        return None
    if request.path not in ("/telegram/webhook", "/"):
        return None

    # 0) Content-Type JSON
    if not _is_json_request(request):
        return jsonify({"error": "content-type must be application/json"}), 415

    # 1) Secret header
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_SECRET_TOKEN:
        return ("unauthorized", 401)

    # 2) Parse JSON tối thiểu
    upd = request.get_json(silent=True) or {}
    upd_id = upd.get("update_id")
    msg = (upd.get("message") or upd.get("edited_message")) or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = msg.get("text")

    # 3) Thiếu dữ liệu cơ bản thì bỏ qua (trả 200 để Telegram không retry vô hạn)
    if not chat_id or text is None:
        logger.info({"event": "skip_update", "reason": "no_chat_or_text", "update_id": upd_id})
        return jsonify({"ok": True}), 200

    # 4) Dedupe theo update_id
    if upd_id in _seen:
        return jsonify({"ok": True}), 200
    _seen.append(upd_id)

    # 5) Rate-limit theo chat
    if not _allow(chat_id):
        _send_text(chat_id, "Nhiều tin nhắn quá 😅 đợi mình tí nhé…")
        return jsonify({"ok": True}), 200

    # Cho phép đi tiếp vào handler chính
    return None


# ============ Basic routes ============
@app.get("/")
def root():
    # Trả 200 gọn để ai bấm URL service cũng thấy OK
    return jsonify(ok=True, service="thienco-bot"), 200


@app.get("/healthz")
def healthz():
    # Endpoint dùng cho smoke test/monitor
    return jsonify(status="ok"), 200


# ============ Webhook handler ============
# Import sau khi setup sys.path
from functions.http.telegram_webhook import telegram_webhook_route  # noqa: E402


@app.post("/telegram/webhook")
def telegram_webhook():
    return telegram_webhook_route()


# Cho phép Telegram trỏ vào "/" nếu cần
@app.post("/")
def webhook_root_alias():
    return telegram_webhook_route()


# ============ Version ============
import datetime  # noqa: E402


@app.get("/version")
def version():
    rev = os.getenv("K_REVISION", "unknown")
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    return {"revision": rev, "built_at": ts}


# ============ Entrypoint ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
