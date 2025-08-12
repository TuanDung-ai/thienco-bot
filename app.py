import os
import sys
import logging
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

@app.get("/")
def root():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200

# Import after sys.path setup
from functions.http.telegram_webhook import telegram_webhook_route  # noqa: E402

@app.post("/telegram/webhook")
def telegram_webhook():
    return telegram_webhook_route()

# Alias to support Telegram pointing to the root path
@app.post("/")
def webhook_root_alias():
    return telegram_webhook_route()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
