
# Thiên Cơ Bot — Starter (GCF Gen2 + Telegram + OpenRouter + Supabase)

> MVP khởi động nhanh: webhook HTTP cho Telegram, gọi LLM qua endpoint OpenAI-compatible,
> log cơ bản (tùy chọn) vào Supabase. Dùng cho Cloud Functions (Gen2).

## 0) Chuẩn bị
- Python 3.11, Git, VS Code
- gcloud (Google Cloud SDK), tài khoản GCP đã bật billing (free tier)
- Telegram bot token từ @BotFather
- (Tùy chọn) Supabase project + Service Role key
- (Khuyên dùng) OpenRouter API key

## 1) Cấu hình môi trường
Sao chép `.env.example` thành `.env` và điền giá trị thực:
```
cp .env.example .env
# Mở .env và thay giá trị TELEGRAM_TOKEN, TELEGRAM_SECRET_TOKEN, LLM_API_KEY, ...
```

## 2) Chạy local (dev)
Cài thư viện và chạy:
```
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
python -m functions_framework --target=telegram_webhook --source=src --port=8080
```

Gửi request thử (giả lập Telegram) với header bí mật khớp TELEGRAM_SECRET_TOKEN:
```
curl -X POST "http://127.0.0.1:8080"   -H "Content-Type: application/json"   -H "X-Telegram-Bot-Api-Secret-Token: your-very-secret-header"   -d @scripts/sample_update.json
```

## 3) Deploy Cloud Functions (Gen2)
```
gcloud functions deploy telegram_webhook   --gen2   --runtime python311   --region=asia-southeast1   --source=./src   --entry-point=telegram_webhook   --trigger-http   --allow-unauthenticated   --set-env-vars="ENV=prod,MAX_TOKENS=512,TEMPERATURE=0.3,MAX_CONTEXT_TOKENS=2000"
```
> Bạn có thể thêm các biến môi trường nhạy cảm qua Secret Manager hoặc `--set-secrets`.
> Với MVP, có thể export biến môi trường từ `.env` rồi `--set-env-vars` tạm thời.

Sau deploy, lấy URL function và gắn webhook:
```
FUNCTION_URL="https://<your-cloud-function-url>"
curl -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook"   -d "url=$FUNCTION_URL"   -d "secret_token=$TELEGRAM_SECRET_TOKEN"
```

## 4) Cấu trúc
```
src/
  core/
    llm_provider.py
    providers/openrouter_provider.py
  infra/
    config.py
    telegram_api.py
    supabase_client.py
    logging.py
  functions/http/telegram_webhook.py
supabase/schema.sql
requirements.txt
.env.example
```

## 5) Lưu ý
- Endpoint LLM mặc định giả định API OpenAI-compatible (`/v1/chat/completions`). Với OpenRouter, đường dẫn là `https://openrouter.ai/api/v1/chat/completions`.
- Nếu provider/đường dẫn thay đổi, chỉnh `LLM_BASE_URL` trong `.env`.
- Không commit `.env`. Dùng Secret Manager khi chuyển production.

## 6) Giấy phép
MIT
