# API Reference

> Platform runtime Base URL: `http://localhost:8709/api/v1`  
> Legacy local-dev examples may mention `http://localhost:8799/api/v1`; root orchestration docs are authoritative for platform runtime.  
> Tất cả response đều wrap trong **ApiResponse envelope** (xem [Response Envelope](#response-envelope)).  
> Tất cả timestamp là **UTC ISO 8601**: `"2026-04-02T10:00:00Z"`

---

## Mục lục

- [Response Envelope](#response-envelope)
- [Error Codes](#error-codes)
- [Naming & Routing Conventions](#naming--routing-conventions)
- [WebSocket](#websocket)
- [Module: Accounts](#module-accounts)
- [Module: Gmail Mailboxes](#module-gmail-mailboxes)
- [Module: Registration](#module-registration)
- [Module: Image Lab](#module-image-lab)
- [Module: Mailbox (temp)](#module-mailbox-temp)
- [Module: Providers](#module-providers)
- [Module: AA Proxy](#module-aa-proxy)
- [Module: Config](#module-config)

---

## Response Envelope

**Mọi endpoint** đều trả về cùng 1 envelope. Client chỉ cần check `success` rồi đọc `data` hoặc `error`.

### Success
```json
{
  "success": true,
  "data": { ... } | [ ... ] | null,
  "error": null,
  "meta": {
    "request_id": "uuid4",
    "ts": "2026-04-02T10:00:00Z"
  }
}
```

### Error
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Human-readable message"
  },
  "meta": {
    "request_id": "uuid4",
    "ts": "2026-04-02T10:00:00Z"
  }
}
```

---

## Error Codes

| Code | HTTP | Ý nghĩa |
|------|------|---------|
| `NOT_FOUND` | 404 | Resource không tồn tại |
| `CONFLICT` | 409 | Đã tồn tại / duplicate |
| `VALIDATION_ERROR` | 400 | Input không hợp lệ |
| `INTERNAL_ERROR` | 500 | Lỗi server không xác định |
| `UNSUPPORTED_SERVICE` | 400 | Service không được hỗ trợ |
| `ALREADY_RUNNING` | 409 | Job/task đang chạy, không thể start thêm |
| `SESSION_EXPIRED` | 401 | Session cookie hết hạn |
| `NO_ACCOUNTS` | 400 | Không có account nào để thực hiện |
| `JOB_CANCELLED` | 400 | Job đã bị cancel |
| `TIMEOUT` | 408 | Operation quá thời gian chờ |

---

## Naming & Routing Conventions

### URL structure
```
/api/v1/{module}/{resource}
/api/v1/{module}/{resource}/{id}
/api/v1/{module}/{resource}/{id}/{action}   ← action endpoint
```



### Router Prefixes
Platform runtime Base URL: `http://localhost:8709/api/v1`  
Moi router co prefix co dinh. **Khong duoc doi** - thay doi se break frontend va docs.

| File router | Prefix | Full base path |
|-------------|--------|----------------|
| `accounts.py` | `/accounts` | `/api/v1/accounts` |
| `gmail.py` | `/gmail` | `/api/v1/gmail` |
| `registration.py` | `/registration` | `/api/v1/registration` |
| `config.py` | `/config` | `/api/v1/config` |
| `mailbox.py` | `/mailbox` | `/api/v1/mailbox` |
| `providers.py` | `/providers` | `/api/v1/providers` |
| `aa_proxy.py` | `/aa` | `/api/v1/aa` |
| `image_lab.py` | `/image-lab` | `/api/v1/image-lab` |

> Khai bao trong `server.py`: tat ca router mount voi `prefix="/api/v1"` + prefix rieng cua router.

---
### Thứ tự khai báo route (BẮT BUỘC)
Route **fixed** phải đứng **TRƯỚC** route có path param trong cùng HTTP method + prefix:
```
# ĐÚNG
POST /mailboxes/refresh-all-sessions   ← fixed route TRƯỚC
POST /mailboxes/{email:path}/refresh-session  ← path param SAU

# SAI — FastAPI sẽ match "refresh-all-sessions" vào {email:path}
POST /mailboxes/{email:path}/refresh-session
POST /mailboxes/refresh-all-sessions
```

### HTTP verbs
| Verb | Dùng khi |
|------|---------|
| `GET` | Đọc dữ liệu, không có side effects |
| `POST` | Tạo mới / trigger action |
| `PATCH` | Update một phần field |
| `PUT` | Replace toàn bộ resource |
| `DELETE` | Xóa resource |

### Background jobs (long-running)
Pattern nhất quán cho mọi operation Playwright/batch:
```
POST /{resource}/start-action     → { "started": true, "task_id": "..." }
GET  /{resource}/start-action/status → { "status": "running|done|error", "progress": {...} }
```
Không dùng `POST` rồi block đợi — luôn async + polling.

---

## WebSocket

### Log streaming
```
WS ws://localhost:8799/api/v1/registration/jobs/{job_id}/logs
WS ws://localhost:8799/api/v1/image-lab/jobs/{job_id}/logs
```

Message format:
```json
{ "level": "info|warn|error", "msg": "...", "ts": "ISO8601" }
```

---

## Module: Accounts

**Prefix:** `/api/v1/accounts`

### Services

#### `GET /accounts/services`
Lấy danh sách tất cả services trong DB (cả có và không có registrar).

**Response `data`:**
```json
["OPENROUTER", "ELEVENLABS", "KLING", "GMAIL", ...]
```

---

#### `POST /accounts/services`
Tạo service mới.

**Request:**
```json
{ "name": "MYSERVICE", "has_registrar": false }
```

**Response `data`:**
```json
{ "created": true, "name": "MYSERVICE" }
```

**Errors:** `VALIDATION_ERROR (400)`, `CONFLICT (409)`

---

#### `DELETE /accounts/services/{name}`
Xóa service theo tên.

**Errors:** `NOT_FOUND (404)`

---

### Accounts CRUD

#### `GET /accounts?service={service}`
Lấy danh sách accounts. `service` là optional filter.

**Response `data`:** `Account[]`

```json
[
  {
    "service": "OPENROUTER",
    "email": "user@gmail.com",
    "api_key": "sk-...",
    "password": "",
    "totp_secret": "",
    "app_password": "",
    "source_email": "",
    "disabled": false,
    "credits": 0,
    "created_at": "2026-04-01T00:00:00Z",
    "updated_at": "2026-04-01T00:00:00Z"
  }
]
```

---

#### `POST /accounts/add`
Thêm account mới.

**Request:**
```json
{
  "service": "OPENROUTER",
  "email": "user@gmail.com",
  "api_key": "sk-...",
  "password": "",
  "totp_secret": "",
  "app_password": "",
  "source_email": ""
}
```

**Response `data`:** `{ "created": true }`

**Errors:** `VALIDATION_ERROR (400)`, `UNSUPPORTED_SERVICE (400)`, `CONFLICT (409)`

---

#### `GET /accounts/{service}/{email}`
Lấy 1 account.

**Errors:** `NOT_FOUND (404)`

---

#### `PATCH /accounts/{service}/{email}`
Update fields của account. Chỉ gửi fields cần update.

**Request:**
```json
{
  "api_key": "sk-new...",
  "disabled": true,
  "credits": 500
}
```

**Response `data`:** `{ "updated": true }`

**Errors:** `NOT_FOUND (404)`

---

#### `DELETE /accounts/{service}/{email}`
Xóa 1 account.

**Response `data`:** `{ "deleted": true }`

**Errors:** `NOT_FOUND (404)`

---

### Bulk Operations

#### `DELETE /accounts/bulk-delete-disabled?service={service}`
Xóa tất cả accounts có `disabled=true`. `service=ALL` (default) → tất cả services.

**Response `data`:** `{ "deleted": 42 }`

---

### Checker

#### `POST /accounts/check?service={service}&email={email}`
Kiểm tra 1 account (API call thực tế).

**Response `data`:** `{ "valid": true, "credits": 500, ... }`

---

#### `POST /accounts/check-all?service={service}`
Start batch check tất cả accounts. Non-blocking.

**Response `data`:** `{ "started": true }`

**Errors:** `ALREADY_RUNNING (409)`

---

#### `GET /accounts/check-all/status`
Poll trạng thái batch check.

**Response `data`:**
```json
{
  "status": "running|done|idle",
  "total": 100,
  "checked": 45,
  "valid": 40,
  "invalid": 5
}
```

---

### OpenRouter Tools

#### `POST /accounts/check-openrouter-privacy`
Start kiểm tra privacy settings của tất cả OR accounts. Non-blocking.

**Errors:** `ALREADY_RUNNING (409)`

---

#### `GET /accounts/check-openrouter-privacy/status`
Poll trạng thái privacy check.

---

#### `POST /accounts/check-and-clean-openrouter`
Test từng OR API key với real API call (minimax model), xóa dead keys khỏi DB + CLIProxy. Non-blocking.

**Errors:** `ALREADY_RUNNING (409)`

---

#### `GET /accounts/check-and-clean-openrouter/status`
Poll trạng thái clean operation.

---

#### `POST /accounts/fix-openrouter-privacy`
Playwright login từng OR account, bật tất cả privacy toggles. Non-blocking.

**Errors:** `ALREADY_RUNNING (409)`

---

#### `GET /accounts/fix-openrouter-privacy/status`
Poll trạng thái fix operation.

---

#### `POST /accounts/key-detail?service={service}&api_key={key}`
Lấy chi tiết về 1 API key (hiện chỉ hỗ trợ OPENROUTER).

**Response `data`:** `{ "valid": true, "credits_used": 1.5, "limit": 10, ... }`

---

### Session Tools

#### `POST /accounts/refresh-kling-session`
Visit app.klingai.com với session hiện có để refresh sliding cookie expiry.

**Request:** `{ "email": "user@gmail.com" }`

**Response `data`:** `{ "refreshed": true }`

**Errors:** `NOT_FOUND (404)`

---

### Sync

#### `POST /accounts/sync-cliproxy`
Đồng bộ tất cả API keys từ DB lên CLIProxy.

---

#### `POST /accounts/sync-openrouter-cliproxy`
Đồng bộ riêng OpenRouter keys lên CLIProxy.

---

#### `POST /accounts/sync-auth`
Sync auth files (JSON session) từ folder `auth/` vào DB.

---

#### `POST /accounts/kling-session`
Persist Kling session từ cookies thủ công.

---

#### `POST /accounts/open-browser`
Mở browser window với session của account chỉ định (headless=false).

---

## Module: Gmail Mailboxes

**Prefix:** `/api/v1/gmail`

Gmail mailbox = credential của hòm thư Gmail để nhận email verification.  
≠ Account: mailbox là inbox, account là tài khoản dịch vụ.

### Schema: `GmailMailbox`
```json
{
  "email": "user@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx",
  "totp_secret": "BASE32SECRET",
  "password": "google-account-password",
  "source_email": "base@gmail.com",
  "google_auth_state": "{...playwright storage_state JSON...}",
  "disabled": false,
  "label": "main",
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

| Field | Mô tả |
|-------|-------|
| `email` | Canonical Gmail address (lowercase, primary key) |
| `app_password` | Gmail App Password cho IMAP — format `xxxx xxxx xxxx xxxx` |
| `totp_secret` | Base32 TOTP secret cho 2FA Google |
| `password` | Google account password — dùng bởi Playwright Google OAuth |
| `source_email` | Base Gmail nếu đây là alias/dot variation |
| `google_auth_state` | Playwright `storage_state()` JSON — rỗng = chưa có session |
| `disabled` | Tạm dừng dùng mailbox này |
| `label` | Tên tuỳ chỉnh: "main", "burner-1", ... |

---

### `GET /gmail/mailboxes`
Lấy tất cả Gmail mailboxes.

**Response `data`:** `GmailMailbox[]`

---

### `POST /gmail/mailboxes`
Thêm hoặc cập nhật mailbox (upsert theo email).

> **Lưu ý:** `google_auth_state` không được gửi qua endpoint này — chỉ được set qua `/refresh-session`.

**Request:**
```json
{
  "email": "user@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx",
  "totp_secret": "",
  "password": "mypassword",
  "source_email": "",
  "label": "main",
  "disabled": false
}
```

**Response `data`:** `GmailMailbox`

**Errors:** `VALIDATION_ERROR (400)` nếu email không phải Gmail hợp lệ

---

### `GET /gmail/mailboxes/{email}`
Lấy 1 mailbox.

**Errors:** `NOT_FOUND (404)`

---

### `DELETE /gmail/mailboxes/{email}`
Xóa 1 mailbox.

**Response `data`:** `{ "deleted": true }`

**Errors:** `NOT_FOUND (404)`

---

### `POST /gmail/mailboxes/refresh-all-sessions`
**⚠️ Route này phải khai báo TRƯỚC `/{email}/refresh-session` trong router.**

Login Google Playwright cho **tất cả** mailboxes có `password` và không `disabled`. Chạy sequential. Mỗi mailbox: email → password → TOTP (nếu có) → lưu `google_auth_state`.

**Response `data`:**
```json
{
  "total": 3,
  "ok": 2,
  "fail": 1,
  "results": [
    { "email": "a@gmail.com", "ok": true },
    { "email": "b@gmail.com", "ok": true },
    { "email": "c@gmail.com", "ok": false, "error": "Không tìm thấy TOTP input" }
  ]
}
```

---

### `POST /gmail/mailboxes/{email}/refresh-session`
Login Google Playwright cho **1** mailbox và lưu `google_auth_state`.

**Google 2FA flow được handle tự động:**
- Case A: Trang TOTP input hiện trực tiếp → fill code ngay
- Case B: Trang "Choose how you want to sign in" → click "Authenticator" option → fill code

**Errors:** `VALIDATION_ERROR (400)` nếu mailbox không có `password`

---


---

### `POST /gmail/mailboxes/{email}/open-browser`
Mở Camoufox browser với `google_auth_state` đã lưu cho mailbox này. **Non-blocking** — trả về ngay, browser chạy trong subprocess riêng.

**Errors:**
- `NOT_FOUND (404)` — mailbox không tồn tại
- `VALIDATION_ERROR (400)` — mailbox chưa có session (chạy `/refresh-session` trước)

**Response `data`:** `{ "launched": true }`
### Gmail Variations

#### `GET /gmail/variations/defaults`
Lấy config mặc định cho Gmail variations.

---

#### `POST /gmail/variations`
Generate tất cả biến thể hợp lệ (dot, plus-tag, googlemail) từ 1 base Gmail.

**Request:** `{ "base_email": "user@gmail.com" }`

---

#### `GET /gmail/used?base_email={email}&service={service}`
Lấy danh sách biến thể đã sử dụng của 1 base email, optionally filtered by service.

---

## Module: Registration

**Prefix:** `/api/v1/registration`

Quản lý auto-registration jobs — Playwright tự động tạo tài khoản dịch vụ.

### `GET /registration/services`
Danh sách services có registrar (có thể auto-register).

**Response `data`:** `["OPENROUTER", "ELEVENLABS", ...]`

---

### `POST /registration/jobs`
Tạo và start registration job.

**Request:**
```json
{
  "service": "OPENROUTER",
  "count": 5,
  "workers": 2
}
```

**Response `data`:** `RegistrationJob`

```json
{
  "id": "uuid4",
  "service": "OPENROUTER",
  "count": 5,
  "workers": 2,
  "status": "running",
  "created_at": "2026-04-02T10:00:00Z",
  "created_count": 0,
  "processed_count": 0,
  "error": null
}
```

**Errors:** `UNSUPPORTED_SERVICE (400)`, `VALIDATION_ERROR (400)`

---

### `GET /registration/jobs`
Lấy tất cả jobs (in-memory, không persist qua restart).

---

### `GET /registration/jobs/{job_id}`
Lấy status của 1 job.

**Errors:** `NOT_FOUND (404)`

---

### `POST /registration/jobs/{job_id}/cancel`
Cancel job đang chạy.

**Errors:** `NOT_FOUND (404)`

---

### `WS /registration/jobs/{job_id}/logs`
Stream real-time logs của job.

```json
{ "level": "info", "msg": "[OPENROUTER] Registering user@gmail.com", "ts": "2026-04-02T10:00:05Z" }
```

---

## Module: Image Lab

**Prefix:** `/api/v1/image-lab`

Tạo ảnh concurrent từ nhiều AA (Artificial Analysis) accounts.

### `POST /image-lab/jobs`
Tạo và start image generation job.

**Request:**
```json
{
  "prompt": "A sunset over mountains",
  "models": ["flux-1.1-pro", "stable-diffusion-3"],
  "aspect_ratio": "1:1 (Square)",
  "dimensions": "1024x1024",
  "generations": 1,
  "workers": 3
}
```

**Response `data`:** `ImageLabJob`

```json
{
  "id": "uuid4",
  "prompt": "A sunset...",
  "models": ["flux-1.1-pro"],
  "aspect_ratio": "1:1 (Square)",
  "dimensions": "1024x1024",
  "generations": 1,
  "workers": 3,
  "status": "running",
  "created_at": "2026-04-02T10:00:00Z",
  "total_accounts": 5,
  "completed_accounts": 0,
  "image_paths": [],
  "error": null
}
```

---

### `GET /image-lab/jobs`
Lấy tất cả jobs.

---

### `GET /image-lab/jobs/{job_id}`
Lấy status + kết quả của 1 job (kể cả `image_paths` sau khi done).

---

### `POST /image-lab/jobs/{job_id}/cancel`
Cancel job.

---

### `WS /image-lab/jobs/{job_id}/logs`
Stream logs.

---

## Module: Mailbox (temp)

**Prefix:** `/api/v1/mailbox`

Quản lý temporary mailboxes từ mail providers (mail.tm, guerrillamail, mailslurp, testmail...).  
Khác với Gmail Mailboxes: đây là inbox tạm, tự động tạo khi đăng ký.

### `POST /mailbox`
Tạo mailbox mới từ provider.

**Request:** `{ "provider": "mail.tm" }` (optional — null = auto-select)

**Response `data`:**
```json
{
  "email": "random@mail.tm",
  "provider": "mail.tm",
  "token": "..."
}
```

---

### `GET /mailbox`
Lấy danh sách active mailboxes trong session hiện tại.

---

### `DELETE /mailbox/{email}`
Xóa mailbox.

---

### `GET /mailbox/{email}/messages`
Lấy danh sách emails trong mailbox.

**Response `data`:** `Message[]`
```json
[
  {
    "id": "msg123",
    "from": "noreply@service.com",
    "subject": "Verify your email",
    "date": "2026-04-02T10:00:00Z",
    "seen": false
  }
]
```

---

### `GET /mailbox/{email}/messages/{message_id}`
Lấy nội dung chi tiết 1 email (body text/html, links).

---

## Module: Providers

**Prefix:** `/api/v1/providers`

Quản lý mail provider configurations + service routing tags.

### `GET /providers`
Lấy danh sách provider domains đang active.

---

### `GET /providers/all`
Lấy tất cả providers + service tags của mỗi provider.

**Response `data`:**
```json
[
  {
    "id": 1,
    "provider_type": "testmail.app",
    "label": "TestMail Main",
    "disabled": false,
    "tags": ["OPENROUTER", "ELEVENLABS"]
  }
]
```

---

### `PATCH /providers/{provider_id}`
Update provider (disable/enable, đổi label).

**Request:** `{ "disabled": true }` hoặc `{ "label": "New Label" }`

---

### `PUT /providers/{provider_domain}/tags`
Thay toàn bộ service tags của provider domain.

**Request:** `{ "tags": ["OPENROUTER", "ELEVENLABS"] }`

---

### `POST /providers/{provider_domain}/tag/{service}/cycle`
Thêm hoặc xóa 1 service tag (toggle).

---

## Module: AA Proxy

**Prefix:** `/api/v1/aa`

Proxy các request đến Artificial Analysis API qua session cookies đã lưu.  
Được dùng bởi Image Lab để gửi generation request.

### `GET /aa/session`
Check session status + balance của account đang được dùng.

---

### `GET /aa/models`
Danh sách image models có sẵn (từ local cache `data/aa_models.json`).

---

### `GET /aa/generations`
Lịch sử generations của account.

---

### `POST /aa/generate`
Tạo generation mới (proxy đến AA API).

**Request:**
```json
{
  "model": "flux-1.1-pro",
  "prompt": "A cat in space",
  "aspect_ratio": "1:1 (Square)",
  "dimensions": "1024x1024"
}
```

---

### `GET /aa/generation/{gen_id}`
Poll status + result của 1 generation.

---

### `GET /aa/image-proxy?url={url}`
Proxy download ảnh từ AA CDN (bypass CORS).

---

### `POST /aa/image-download`
Download và lưu ảnh về local disk.

---

## Module: Config

**Prefix:** `/api/v1/config`

Đọc/ghi config files trong thư mục `config/`.

### `GET /config/files`
Danh sách tất cả files trong config dir.

**Response `data`:** `{ "files": ["config.yaml", "proxies.yaml"] }`

---

### `GET /config/raw?file={filename}`
Đọc raw content của 1 config file.

**Response `data`:** `{ "content": "...", "file": "config.yaml" }`

**Errors:** `NOT_FOUND (404)`

---

### `PUT /config/raw?file={filename}`
Ghi đè content của 1 config file. Validate YAML trước khi save.

**Request:** `{ "content": "yaml content here" }`

**Errors:** `VALIDATION_ERROR (400)` nếu YAML invalid

---

### `POST /config/mail/add-key`
Thêm MailSlurp API key vào config.

**Request:** `{ "key": "ms_key_..." }`

**Response `data`:** `{ "total": 5 }` (total keys sau khi thêm)

---

### `GET /config`
Lấy parsed config dưới dạng dict.

---

## Phụ lục: Common Patterns

### Pattern 1 — Polling background job
```
POST /resource/start-action
  → { "started": true }

loop:
  GET /resource/start-action/status
  → { "status": "running", "progress": { "done": 3, "total": 10 } }
  wait 2s

GET /resource/start-action/status
  → { "status": "done", "results": [...] }
```

### Pattern 2 — Path param sau fixed route
```python
# ĐÚNG — fixed routes TRƯỚC path params
@router.post("/mailboxes/refresh-all-sessions")  # fixed
@router.post("/mailboxes/{email:path}/refresh-session")  # param

# SAI
@router.post("/mailboxes/{email:path}/refresh-session")
@router.post("/mailboxes/refresh-all-sessions")  # bị nuốt bởi {email:path}
```

### Pattern 3 — Async / non-blocking
- Operations dài (Playwright, batch check) → luôn **non-blocking**: return ngay, client poll status
- Operations nhanh (DB read/write) → có thể blocking trong `asyncio.to_thread`
- Không bao giờ block event loop bằng sync I/O trực tiếp

### Pattern 4 — Error handling
```python
# ĐÚNG — ném lỗi cụ thể
if not record:
    raise AppError(ErrorCode.NOT_FOUND, f"Mailbox không tồn tại: {email!r}", 404)

# SAI — nuốt lỗi
try:
    ...
except Exception:
    pass
```
