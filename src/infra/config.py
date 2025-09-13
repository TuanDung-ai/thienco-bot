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
    try:
        val = val.encode("utf-8").decode("utf-8-sig")
    except Exception:
        pass
    return val.strip()

def _to_int(val: str | None, default: int) -> int:
    try:
        v = (_clean(val) or "").strip()
        return int(v) if v != "" else default
    except Exception:
        return default

def _to_float(val: str | None, default: float) -> float:
    try:
        v = (_clean(val) or "").strip()
        return float(v) if v != "" else default
    except Exception:
        return default

class Settings(BaseModel):
    # --- BẮT BUỘC / LLM / TELEGRAM ---
    TELEGRAM_TOKEN: str
    TELEGRAM_SECRET_TOKEN: str
    LLM_API_KEY: str
    LLM_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    LLM_BASE_URL: str = "https://openrouter.ai/api"
    LLM_PROVIDER: str = "openrouter"

    # --- SUPABASE (có thể bỏ trống -> tính năng DB sẽ bỏ qua) ---
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    # --- CẤU HÌNH CHUNG ---
    ENV: str = "dev"
    MAX_TOKENS: int = 512
    TEMPERATURE: float = 0.3
    MAX_CONTEXT_TOKENS: int = 2000

    # --- MỚI: TỐI ƯU CHAT ---
    MAX_INPUT: int = 1000          # cắt chiều dài input để tiết kiệm chi phí
    LLM_TIMEOUT: int = 8           # giây, timeout cho gọi LLM

    # --- MỚI: BỘ NHỚ & NGỮ CẢNH ---
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    MEMORY_TOPK: int = 8           # số mảnh ngữ cảnh lấy vào prompt
    SUMMARY_EVERY_N: int = 12      # tóm tắt sau mỗi N tin (nếu bật summarize)
    TIMEZONE_DEFAULT: str = "Asia/Ho_Chi_Minh"

def load_settings_from_env() -> Settings:
    fields = {
        # LLM/TELEGRAM
        "TELEGRAM_TOKEN": _clean(os.environ.get("TELEGRAM_TOKEN", "")),
        "TELEGRAM_SECRET_TOKEN": _clean(os.environ.get("TELEGRAM_SECRET_TOKEN", "")),
        "LLM_API_KEY": _clean(os.environ.get("LLM_API_KEY", "")),
        "LLM_MODEL": _clean(os.environ.get("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct:free")),
        "LLM_BASE_URL": _clean(os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api")),
        "LLM_PROVIDER": _clean(os.environ.get("LLM_PROVIDER", "openrouter")),

        # Supabase
        "SUPABASE_URL": _clean(os.environ.get("SUPABASE_URL")),
        "SUPABASE_SERVICE_ROLE_KEY": _clean(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),

        # Chung
        "ENV": _clean(os.environ.get("ENV", "dev")),
        "MAX_TOKENS": _to_int(os.environ.get("MAX_TOKENS"), 512),
        "TEMPERATURE": _to_float(os.environ.get("TEMPERATURE"), 0.3),
        "MAX_CONTEXT_TOKENS": _to_int(os.environ.get("MAX_CONTEXT_TOKENS"), 2000),

        # MỚI: tối ưu chat
        "MAX_INPUT": _to_int(os.environ.get("MAX_INPUT"), 1000),
        "LLM_TIMEOUT": _to_int(os.environ.get("LLM_TIMEOUT"), 8),

        # MỚI: bộ nhớ & ngữ cảnh
        "EMBED_MODEL": _clean(os.environ.get("EMBED_MODEL", "text-embedding-3-small")),
        "MEMORY_TOPK": _to_int(os.environ.get("MEMORY_TOPK"), 8),
        "SUMMARY_EVERY_N": _to_int(os.environ.get("SUMMARY_EVERY_N"), 12),
        "TIMEZONE_DEFAULT": _clean(os.environ.get("TIMEZONE_DEFAULT", "Asia/Ho_Chi_Minh")),
    }

    # Clamp nhẹ để tránh cấu hình “bậy”
    if fields["MEMORY_TOPK"] < 1: fields["MEMORY_TOPK"] = 1
    if fields["MEMORY_TOPK"] > 32: fields["MEMORY_TOPK"] = 32
    if fields["MAX_TOKENS"] < 64: fields["MAX_TOKENS"] = 64
    if fields["MAX_TOKENS"] > 4096: fields["MAX_TOKENS"] = 4096
    if fields["TEMPERATURE"] < 0: fields["TEMPERATURE"] = 0.0
    if fields["TEMPERATURE"] > 1: fields["TEMPERATURE"] = 1.0
    if fields["LLM_TIMEOUT"] < 3: fields["LLM_TIMEOUT"] = 3

    return Settings(**fields)
