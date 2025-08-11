
import httpx
from .logging import log

BASE = "https://api.telegram.org"

async def send_message(token: str, chat_id: int, text: str, parse_mode: str | None = None):
    url = f"{BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, json=payload)
        log("telegram sendMessage status:", r.status_code)
        if r.status_code != 200:
            log("telegram error:", r.text)
        return r.json()
