# src/core/llm_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel
from pathlib import Path

class ChatMessage(BaseModel):
    role: str
    content: str

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[ChatMessage], max_tokens: int, temperature: float) -> str:
        ...

def build_system_prompt() -> str:
    p = Path("prompts/persona_system_vi.txt")
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    # fallback cũ
    return (
        "Bạn là Thiên Cơ – trợ lý trung thực, hài hước, chính xác. "
        "Luôn giải thích thuật ngữ [trong ngoặc vuông] lần đầu xuất hiện. "
        "Giữ câu trả lời ngắn gọn, rõ ràng, từng bước khi cần."
    )
