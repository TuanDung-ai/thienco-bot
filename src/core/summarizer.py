import os
from typing import List, Dict
import httpx

BASE = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api").rstrip("/")
API  = os.getenv("LLM_API_KEY", "")
MODEL= os.getenv("LLM_MODEL", "openai/gpt-3.5-turbo")

_summary_sys = "Tóm tắt ≤120 từ, liệt kê 3–5 ý chính & quyết định đã chốt."
_facts_sys   = "Trích 3–5 'sự thật bền' hữu ích lâu dài; tránh dữ liệu nhạy cảm."

async def _chat(messages: List[Dict[str,str]]) -> str:
    url = f"{BASE}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {API}"}
    payload = {"model": MODEL, "temperature": 0.2, "messages": messages}
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

async def summarize_window(messages: List[Dict[str,str]]) -> str:
    return await _chat([{"role":"system","content":_summary_sys}] + messages)

async def extract_facts(messages: List[Dict[str,str]]) -> List[str]:
    text = await _chat([{"role":"system","content":_facts_sys}] + messages)
    facts = [ln.strip("-• ").strip() for ln in text.splitlines() if ln.strip()]
    return [f for f in facts if len(f) > 3]
