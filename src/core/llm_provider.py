
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str
    content: str

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[ChatMessage], max_tokens: int, temperature: float) -> str:
        ...

def build_system_prompt() -> str:
    return (
        "Bạn là Thiên Cơ – trợ lý trung thực, hài hước, chính xác. "
        "Luôn giải thích thuật ngữ [trong ngoặc vuông] lần đầu xuất hiện. "
        "Giữ câu trả lời ngắn gọn, rõ ràng, từng bước khi cần."
    )
