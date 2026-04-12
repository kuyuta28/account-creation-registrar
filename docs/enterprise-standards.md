# Enterprise Standards — registrar

> Tài liệu chuẩn hóa hệ thống. Mọi module mới **PHẢI** tuân thủ trước khi merge.

---

## 1. Error Taxonomy

### Nguyên tắc
- **CẤM** dùng `RuntimeError` trực tiếp — phải dùng error class từ hierarchy.
- **CẤM** match lỗi bằng string (`"some error" in str(exc)`) — phải dùng `isinstance()`.
- **CẤM** nuốt lỗi (`except: pass`, `except Exception: pass`) — phải raise hoặc log + raise.
- Mỗi error class thuộc đúng 1 nhánh, dispatcher tự biết cách xử lý.

### Hierarchy (common/errors.py)

```
AppError (base)
├── RegistrationError       → lỗi trong flow đăng ký account
├── MailError               → lỗi liên quan đến mailbox/email provider
├── GoogleAuthError         → lỗi trong Google OAuth / login flow
├── CaptchaError             → captcha solve thất bại
├── BrowserError             → Playwright browser / page error
├── ConfigError              → config sai / thiếu setting
└── DatabaseError            → lỗi database layer
```

### API Error Hierarchy (src/api/exceptions.py)

```
AppError (base, từ common.errors)
  → FastAPI exception handlers tự convert thành ApiResponse envelope
  → 4 handlers: app_error_handler, validation_error_handler, http_exception_handler, generic_error_handler
```

### File: `common/src/common/errors.py`, `src/api/exceptions.py`

---

## 2. API Response Envelope

### Chuẩn
Mọi endpoint trả cùng 1 format:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "ts": "2026-04-03T06:37:09Z"
  }
}
```

Khi lỗi:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Không còn mailbox khả dụng cho service ELEVENLABS"
  },
  "meta": { ... }
}
```

### ErrorCode enum (common/enums.py)
NOT_FOUND, CONFLICT, VALIDATION_ERROR, INTERNAL_ERROR, UNSUPPORTED_SERVICE, ALREADY_RUNNING, SESSION_EXPIRED, NO_ACCOUNTS, JOB_CANCELLED, TIMEOUT

### File: `src/api/schemas.py`, `src/api/exceptions.py`

---

## 3. Logging

### Nguyên tắc
- **Log 1 dòng per action** — không log intermediate steps ("Looking for...", "Found...", "Clicking...").
- **Truncate URL** — dùng `_short_url()`, bỏ query string.
- **Không print HTML** ra console — chỉ ghi file vào `debug/`.
- **Log level đúng**: DEBUG cho trace, INFO cho action summary, WARNING cho recoverable, ERROR cho failure.
- **Dependency injection** — inject `LogFn` vào function, không dùng global logger trong service layer.

### File: `common/src/common/logger.py`

---

## 4. Config

### Nguyên tắc
- **Frozen dataclass** — immutable sau khi tạo.
- **Strict parsing** — `_parse_section_strict()` validate schema.
- **CẤM hardcode** giá trị — mọi thứ phải đọc từ config YAML hoặc env var.
- **Type-safe** — không dùng `Any`, không dùng `dict` khi có thể dùng dataclass.

### File: `src/config/settings.py`
### Config files: `config/*.yaml`

---

## 5. Service Architecture

### Protocol
Mọi registrar tuân thủ interface:

```python
async def register_xxx(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> Optional[AccountRecord]:
```

### Nguyên tắc
- **FP only** — pure functions, không OOP, không global state.
- **Async & concurrent** — tận dụng `asyncio`, cấm blocking IO.
- **Dependency injection** — inject cfg, log_fn, save_fn. Không import global.
- **SRP** — mỗi file ≤ 200 dòng, mỗi function làm đúng 1 việc.
- **CẤM fallback** — flow sai = raise exception, không try hướng khác.

### Service Registry: `src/services/registry.py`

---

## 6. Database

### Nguyên tắc
- **SQLAlchemy ORM** + SQLite (WAL mode).
- **NullPool** — không connection pooling (Playwright cleanup).
- **Idempotent migrations** — ALTER TABLE IF NOT EXISTS.
- **Service blocks** — `mailbox_service_blocks` table ngăn email bị chọn lại.
- **Index đúng** — (service, disabled), (service, email unique).
- **PRAGMA** — busy_timeout=5000, synchronous=NORMAL.
- **Retry** — `_retry_db_op()` cho "database is locked" errors.

### File: `common/src/common/database/`

---

## 7. Browser Automation (Registrar)

### Quy trình BẮT BUỘC khi viết service mới

1. **Dùng Playwright lấy HTML rendered** — KHÔNG dùng `requests.get()`.
2. **Dump & phân tích DOM** — liệt kê buttons, inputs, tabs, dialogs.
3. **Xác định thứ tự tương tác** — skip OAuth buttons, check tab UI.
4. **Code dựa trên DOM thực tế** — không đoán.
5. **Dump HTML sau mỗi action** khi debug — production chỉ dump khi error.

### Nguyên tắc
- Dùng **Playwright locator** (`.click()`, `.fill()`) — không dùng `evaluate()` cho React state.
- **CẤM hardcode selector** — phải flexible.
- Log **1 dòng per action**, URL truncated.

---

## 8. Testing

### Structure
```
tests/
├── unit/          # Không network, không browser. Mock everything.
├── integration/   # Có DB, có config. Không browser.
├── e2e/           # Full flow với browser.
└── conftest.py    # Shared fixtures
```

### Nguyên tắc
- Mọi module mới phải có unit test.
- Mock external dependencies (`@patch`).
- Test cả happy path lẫn error path.

---

## 9. Monitoring & Observability

### Đã có
- **Sentry** — error tracking, async + FastAPI integration.
- **File logs** — rotation 10MB × 5 backups.
- **all.log** — tee stdout + stderr.

### Cần bổ sung khi scale
- Health check endpoint (`/health`)
- Request tracing (correlation ID via meta.request_id)
- Metrics (Prometheus)
- Graceful shutdown (signal handlers)

---

## 10. Code Quality

### Enforced
- **Ruff** — BLE001 (no blind except), E722 (no bare except), UP (pyupgrade).
- **Pre-commit** — ruff check on `src/`.
- **Frozen dataclass** — immutable config & records.

### Nguyên tắc chung
- Nói tiếng Việt trong comments/docs.
- FP style — tránh OOP.
- Mỗi file ≤ 200 dòng.
- Không dùng `Any`.
- Không tự viết lại lib có sẵn.