
import os, requests, json

# Simple health check for deployed function (replace URL)
FUNCTION_URL = os.environ.get("FUNCTION_URL", "https://your-function-url")
SECRET = os.environ.get("TELEGRAM_SECRET_TOKEN", "your-very-secret-header")

sample = {
  "update_id": 42,
  "message": {
    "message_id": 1,
    "from": {"id": 1, "is_bot": False, "first_name": "HC"},
    "chat": {"id": 1, "type": "private"},
    "date": 1700000000,
    "text": "ping"
  }
}

r = requests.post(FUNCTION_URL, headers={
  "Content-Type": "application/json",
  "X-Telegram-Bot-Api-Secret-Token": SECRET
}, data=json.dumps(sample))

print("Status:", r.status_code)
print(r.text)
