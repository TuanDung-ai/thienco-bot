import httpx
from typing import List
from ..infra.logging import log, log_error  # ✅ Sửa import relative
from ..llm_provider import LLMProvider, ChatMessage  # ✅ Sửa import relative

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        # Expect base_url like 'https://openrouter.ai/api' or an OpenAI-compatible base
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/v1/chat/completions"

    async def chat(self, messages: List[ChatMessage], max_tokens: int, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(self.endpoint, headers=headers, json=payload)
                if r.status_code != 200:
                    log_error("LLM error:", r.status_code, r.text)
                    raise RuntimeError(f"LLM error: {r.status_code}")
                data = r.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    log_error("Unexpected LLM response format:", data)
                    raise RuntimeError(f"Invalid LLM response format: {e}")
        except httpx.TimeoutException:
            log_error("LLM request timeout")
            raise RuntimeError("LLM request timeout")
        except Exception as e:
            log_error("LLM request failed:", str(e))
            raise
