import os
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("thienco-bot")

@app.get("/")
def health():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200

# Cố gắng dùng handler có sẵn (nếu bạn đã viết ở functions/http/telegram_webhook.py)
_HANDLER = None
try:
    from functions.http.telegram_webhook import telegram_webhook as _FUNC_HANDLER  # type: ignore
    _HANDLER = _FUNC_HANDLER
    logger.info("Loaded handler from functions/http/telegram_webhook.py")
except Exception as e:
    logger.warning("No custom handler found at functions/http/telegram_webhook.py; using default stub. Error: %s", e)

@app.post("/telegram-webhook")
def telegram_webhook_route():
    if _HANDLER:
        # chuyển tiếp request cho handler kiểu "Cloud Functions"
        return _HANDLER(request)
    # Stub mặc định: chỉ nhận và trả 200 cho Telegram
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    logger.info("Received webhook: %s", data)
    return jsonify(ok=True), 200

# Chạy local/dev: Cloud Run sẽ dùng Procfile + gunicorn, không gọi nhánh này
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
