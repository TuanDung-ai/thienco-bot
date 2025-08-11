from pydantic import BaseModel
import os

def _clean(val: str | None) -> str | None:
    """
    Làm sạch giá trị lấy từ env/secrets:
    - Bỏ BOM (utf-8-sig)
    - strip() để loại \r, \n, khoảng trắng đầu/cuối
    Trả về None nếu đầu vào là None.
    """
    if val is None:
        return None
    # decode lại để loại BOM nếu có
    try:
        val = val.encode('utf-8').decode('utf-8-sig')
    except Exception:
        # phòng hờ trường hợp giá trị đã là str sạch
        pass
    return val.strip()

class Settings(BaseModel):
    TELEGRAM_TOKEN: str
    TELEGRAM_SECRET_TOKEN: str
    LLM_API_KEY: str
    LLM_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api"
    LLM_PROVIDER: str = "openrouter"

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    ENV: str = "dev"
    MAX_TOKENS: int = 512
    TEMPERATURE: float = 0.3
    MAX_CONTEXT_TOKENS: int = 2000

def load_settings_from_env() -> Settings:
    # Lấy và làm sạch tất cả biến môi trường cần thiết
    fields = {
        "TELEGRAM_TOKEN": _clean(os.environ.get("TELEGRAM_TOKEN", "")),
        "TELEGRAM_SECRET_TOKEN": _clean(os.environ.get("TELEGRAM_SECRET_TOKEN", "")),
        "LLM_API_KEY": _clean(os.environ.get("LLM_API_KEY", "")),
        "LLM_MODEL": _clean(os.environ.get("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct:free")),
        "LLM_BASE_URL": _clean(os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api")),
        "LLM_PROVIDER": _clean(os.environ.get("LLM_PROVIDER", "openrouter")),
        "SUPABASE_URL": _clean(os.environ.get("SUPABASE_URL")),
        "SUPABASE_SERVICE_ROLE_KEY": _clean(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
        "ENV": _clean(os.environ.get("ENV", "dev")),
        # các giá trị số không cần clean nhưng vẫn an toàn nếu có khoảng trắng
        "MAX_TOKENS": int(_clean(os.environ.get("MAX_TOKENS", "512")) or "512"),
        "TEMPERATURE": float(_clean(os.environ.get("TEMPERATURE", "0.3")) or "0.3"),
        "MAX_CONTEXT_TOKENS": int(_clean(os.environ.get("MAX_CONTEXT_TOKENS", "2000")) or "2000"),
    }
    return Settings(**fields)
