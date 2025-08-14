# Hướng dẫn Triển khai Chi Tiết — Thiên Cơ Bot (Kế hoạch tối giản)
> Bản này được sinh ra từ **KeHoachToiGian_BotThienCo.xlsx**. Mục tiêu: làm theo là chạy, ít người dùng, chi phí ≈ 0.

## Nguyên tắc chung
- Luôn ưu tiên **đơn giản** và **an toàn** trước: không thêm tính năng nếu không cần.
- Không log token hoặc nội dung chat nhạy cảm. Dùng placeholder khi test.
- Mọi thay đổi đều đi qua chu trình: **local test → deploy canary (10%) → quan sát log 10 phút → chuyển 100%**.

---

## I. Các mục cần làm (TODO/PARTIAL)
- [0.3] **Ghép URL OpenRouter an toàn** — *0 - Nền tảng / LLM* · Trạng thái: **TODO** · Ghi chú: Ghép URL an toàn
- [1.2] **Timeout + Retry/backoff** — *1 - Ổn định / LLM* · Trạng thái: **TODO** · Ghi chú: Timeout+Retry
- [1.5] **Không log token/nội dung nhạy cảm** — *1 - Ổn định / An toàn* · Trạng thái: **TODO** · Ghi chú: Không log nhạy cảm
- [2.1] **Cắt lịch sử dài (budget)** — *2 - Chi phí / Prompt* · Trạng thái: **TODO** · Ghi chú: Trim history
- [3.1] **Bật RLS theo chat_id** — *3 - Bảo mật / RLS* · Trạng thái: **TODO** · Ghi chú: RLS
- [3.2] **Rotate secrets định kỳ** — *3 - Bảo mật / Secrets* · Trạng thái: **TODO** · Ghi chú: Rotate secrets
- [4.1] **/version endpoint** — *4 - Bảo trì / Thông tin* · Trạng thái: **TODO** · Ghi chú: /version endpoint
- [4.3] **Unit test tối thiểu** — *4 - Bảo trì / Test* · Trạng thái: **TODO** · Ghi chú: Unit tests


---
## II. Thực hiện theo từng mục (bước-by-bước + code)

### [0.3] Ghép URL OpenRouter an toàn (TODO)
**Mục tiêu:** Tránh lỗi `/v1/v1` → HTTP 405.  
**Bước làm:**
1) Trong module gọi LLM, thêm logic ghép URL an toàn:
```python
from urllib.parse import urljoin
import os

base = os.getenv("LLM_BASE_URL", "").rstrip("/") + "/"
endpoint = "v1/chat/completions"
LLM_URL = urljoin(base, endpoint)  # tránh /v1/v1
```
2) Kiểm tra nhanh:
```bash
python - <<'PY'
from urllib.parse import urljoin
tests = [
    ("https://openrouter.ai/api/", "v1/chat/completions"),
    ("https://openrouter.ai/api", "v1/chat/completions"),
    ("https://api.openrouter.ai/v1", "chat/completions"),
]
for b,e in tests:
    print(b, "->", urljoin(b.rstrip('/')+'/', e))
PY
```
3) Smoke test từ Cloud Shell:
```bash
curl -s -X POST "$LLM_URL" -H "Authorization: Bearer $LLM_API_KEY" -H "Content-Type: application/json" -d '{"model":"openrouter/auto","messages":[{"role":"user","content":"ping"}]}' | head
```

### [1.1] Validate method/Content-Type (nếu PARTIAL)
**Mục tiêu:** Chỉ nhận POST + JSON, chặn input bẩn.  
**Code (Flask route /webhook):**
```python
from flask import request, jsonify

ALLOWED_CT = {"application/json", "application/json; charset=utf-8"}

def is_json_request(req):
    ct = (req.headers.get("Content-Type") or "").lower()
    return any(ct.startswith(a.lower()) for a in ALLOWED_CT)

@app.post("/telegram/webhook")
def webhook():
    if not is_json_request(request):
        return jsonify({"error":"content-type must be application/json"}), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error":"invalid json"}), 400
    # ... xử lý tiếp
```
**Test:** gửi request sai CT: `curl -H "Content-Type: text/plain" ...` → phải trả 415.

### [1.2] Timeout + Retry/backoff (nếu PARTIAL)
**Mục tiêu:** Chống mạng chập chờn, không treo request lâu.
```python
import httpx, time, random

TIMEOUT = httpx.Timeout(10.0, read=15.0)
RETRY_MAX = 3

def call_llm(payload):
    last_err = None
    for attempt in range(RETRY_MAX):
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.post(LLM_URL, json=payload)
                if r.status_code < 500:
                    return r
        except httpx.RequestError as e:
            last_err = e
        time.sleep((2**attempt) + random.random())  # jitter
    raise RuntimeError(f"LLM call failed after retries: {last_err}")
```

### [1.3] Fast-path /start,/help (nếu TODO)
**Mục tiêu:** Trả nhanh, không gọi LLM.
```python
FAST_REPLIES = {
    "/start": "Xin chào! Mình là Thiên Cơ. Gõ /help để xem hướng dẫn.",
    "/help": "Mình hỗ trợ trò chuyện, checklist, và gợi ý. Cứ nhắn tự nhiên nhé!"
}

def handle_fastpath(text: str):
    t = (text or "").strip().lower()
    return FAST_REPLIES.get(t)
```

### [1.4] Fallback an toàn khi LLM fail (đánh giá thủ công)
**Mục tiêu:** Không crash, vẫn phản hồi lịch sự.
```python
def safe_fallback(reason: str = ""):
    msg = "Xin lỗi, mình đang hơi bận. Bạn thử lại sau một chút nhé."
    if reason:
        # ghi log nội bộ, **không** gửi reason ra ngoài
        pass
    return msg
```

### [1.5] Không log nhạy cảm; giảm noise (nếu PARTIAL)
**Bước làm:**
- Thiết lập logger:
```python
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
```
- Khi log, chỉ ghi độ dài, không ghi nội dung:
```python
logger.info("telegram_out", extra={"len": len(text), "chat_id": chat_id})
```

### [2.1] Cắt lịch sử dài (token budget) (nếu TODO)
```python
def trim_history(messages, max_chars=6000):
    s = 0; kept = []
    for m in reversed(messages):
        s += len(m.get("content",""))
        kept.append(m)
        if s > max_chars: break
    return list(reversed(kept))
```

### [2.2] Gửi typing action (nếu TODO)
```python
def send_typing(chat_id: int):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    httpx.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=10)
```

### [2.3] Chỉ lưu trường cần thiết (nếu PARTIAL)
- **Schema tối thiểu** (Supabase SQL):
```sql
create table if not exists messages (
  id bigint generated by default as identity primary key,
  conversation_id text,
  chat_id text not null,
  role text check (role in ('user','assistant','system')),
  content text,
  created_at timestamptz default now()
);
create index if not exists idx_messages_chat_time on messages(chat_id, created_at desc);
```
- Khi insert: chỉ `chat_id, role, content, (optional) conversation_id`.

### [3.1] RLS theo chat_id (manual TODO)
> Thực hiện trong Supabase SQL Editor.
```sql
-- Bật RLS
alter table messages enable row level security;

-- Cho phép insert từ server (service_role key) — an toàn vì thực hiện từ backend của bạn.
create policy "server can insert" on messages
for insert to public with check (true);

-- Hạn chế select (nếu sau này dùng auth, gắn theo X-Hasura-... hoặc JWT claims)
create policy "select by chat_id" on messages
for select using (chat_id = current_setting('request.jwt.claims.chat_id', true));
```
> Giai đoạn 1 user → có thể **không** mở select công khai; chỉ server đọc/ghi.

### [3.2] Rotate secrets định kỳ (manual TODO)
- Ghi chú ngày phát hành secrets trong README.  
- Mỗi 3–6 tháng: tạo key mới → cập nhật Cloud Run env → redeploy → xoá key cũ.  
- Kiểm tra webhook Telegram có **secret_token** đúng.

### [4.1] /version endpoint (nếu TODO)
```python
import os, datetime
@app.get("/version")
def version():
    rev = os.getenv("K_REVISION","unknown")
    ts = datetime.datetime.utcnow().isoformat()+"Z"
    return {"revision": rev, "built_at": ts}
```

### [4.2] Config tập trung (nếu TODO)
```python
# config.py
import os

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))
TIMEOUT_CONNECT = float(os.getenv("TIMEOUT_CONNECT", "10"))
TIMEOUT_READ = float(os.getenv("TIMEOUT_READ", "15"))
```

### [4.3] Unit test tối thiểu (nếu TODO)
- Cài: `pip install pytest`
- Test HMAC/secret header & URL join:
```python
# tests/test_urljoin.py
from urllib.parse import urljoin
def test_urljoin_variants():
    base_cases = ["https://api.openrouter.ai/", "https://api.openrouter.ai"]
    for b in base_cases:
        assert urljoin(b.rstrip('/')+'/', "v1/chat/completions").endswith("/v1/chat/completions")
```

---

## III. Quy trình deploy an toàn (Cloud Run)
1) Build & deploy:
```bash
gcloud run deploy thienco-bot   --source .   --region=asia-southeast1   --allow-unauthenticated   --set-env-vars=TELEGRAM_TOKEN=***,TELEGRAM_SECRET_TOKEN=***,LLM_API_KEY=***,LLM_BASE_URL=https://api.openrouter.ai   --min-instances=0 --max-instances=3
```
2) Set webhook (chỉ làm 1 lần hoặc khi đổi URL/secret):
```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook"   -H "Content-Type: application/json"   -d '{"url":"https://<cloud-run-url>/telegram/webhook","secret_token":"'$TELEGRAM_SECRET_TOKEN'","allowed_updates":["message","edited_message","callback_query","inline_query"]}'
```
3) Smoke tests:
```bash
curl -s https://<cloud-run-url>/healthz
curl -s https://api.telegram.org/bot$TELEGRAM_TOKEN/getWebhookInfo | jq
```

---

## IV. Checklist xác nhận (tick xong là done)
- [ ] 0.3 URL LLM an toàn → curl 200 OK
- [ ] 1.1 Content-Type/Method validation chạy đúng
- [ ] 1.2 Timeout+Retry có hiệu lực (mô phỏng fail 1–2 lần)
- [ ] 1.3 Fast-path hoạt động với /start,/help
- [ ] 1.4 Fallback trả tin nhắn lịch sự khi LLM lỗi
- [ ] 2.1 Trim history cắt bớt khi hội thoại dài
- [ ] 2.2 Typing action xuất hiện trước khi trả lời
- [ ] 2.3 DB chỉ lưu trường cần thiết
- [ ] 3.1 RLS bật (nếu cần)
- [ ] 3.2 Secrets note & quy trình rotate lưu trong README
- [ ] 4.1 /version trả revision
- [ ] 4.2 config.py có biến chung
- [ ] 4.3 pytest chạy pass

---

## V. Lệnh tra log nhanh (Cloud Shell)
```bash
SERVICE=thienco-bot
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name='$SERVICE   --limit=100 --freshness=30m --format="value(textPayload)" --order=desc
```

Hoàn tất! Làm theo thứ tự các mục TODO → PARTIAL là ổn.
