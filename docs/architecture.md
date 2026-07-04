# Architecture

> Runtime note: root orchestration publishes `registrar`, `mail-service`, `aa-proxy`, and `tts-proxy` on ports `8709`, `8701`, `8702`, and `8700`. Older service-local examples in this document that mention `8799` or `880x` are legacy local-dev references.

## Repository Structure

```
account-creation/          ← root container (không có git)
├── registrar/             ← core service (git riêng, port 8799)
├── aa-proxy/              ← image proxy (git riêng, port 8802)
├── tts-proxy/             ← TTS proxy (git riêng, port 8800)
├── mail-service/          ← mail service (git riêng, port 8801)
```

Mỗi service **độc lập**: git riêng, pyproject riêng, run độc lập. Root là plain folder container, không có `.git`.

---

## registrar/ — Core Service

**Mục đích**: Đăng ký tài khoản tự động trên các AI/SaaS platform.

**Stack**: FastAPI · Playwright/Camoufox · asyncio concurrent jobs

**Phân tầng**:
```
src/
  api/           ← FastAPI routes
  services/      ← registrar per platform (proton, klingai...)
  mail/          ← mail provider clients (mail.tm, testmail.app)
  core/          ← job runner, browser manager, config loader
ui/              ← frontend (Vite/React)
config/          ← per-service YAML configs
```

**Communication**: registrar gọi `tts-proxy` qua HTTP, `mail-service` qua HTTP.

### Mail Providers

| Provider | Notes |
|----------|-------|
| `mail.tm` | Free, no-auth REST |
| `testmail.app` | Free tier, namespace + API key |

### Service Registrars

| Key | Domain |
|-----|--------|
| `OPENROUTER` | openrouter.ai |
| `CHATGPT` | chatgpt.com |
| `ELEVENLABS` | elevenlabs.io |
| `LEONARDO` | leonardo.ai |
| `KLINGAI` | klingai.com |
| `PROTON` | proton.me |
| `ARTIFICIALANALYSIS` | artificialanalysis.ai |

---

## Error Hierarchy (registrar)

```
RegistrationError
├── FatalRegistrationError       → dừng job
│   ├── NoMailboxAvailableError
│   ├── InvalidConfigError
│   └── NoSessionError
├── RetryableRegistrationError   → retry
│   ├── CaptchaError
│   ├── PageTimeoutError
│   └── EmailVerificationError
└── PermanentAccountError        → skip, tiếp tục
    ├── AccountAlreadyExistsError
    └── AccountBannedError
```

---

## aa-proxy/ — Image Proxy

See `aa-proxy/docs/`.

## tts-proxy/ — TTS Proxy

See `tts-proxy/docs/`.

## mail-service/ — Mail Service

See `mail-service/docs/`.


---

## Phân tầng: Inbox Providers vs Service Registrars

Codebase chia rõ 2 tầng:

### Tầng 1 — Inbox Providers (bên cung mail) `src/mail/providers/`

Cung cấp hộp thư tạm thời để nhận email xác minh.

| File | Domain | Ghi chú |
|------|--------|---------|
| `mail_tm.py` | mail.tm | Free, no-auth REST |
| `testmail_app.py` | testmail.app | Free tier, namespace + API key |

Public interface của mỗi provider:
- `create_mailbox(provider_str) -> Mailbox`
- `get_messages(box) -> List[Dict]`
- `get_message_body(box, msg_id) -> str`
- `wait_for_message(box, ...) -> Optional[Dict]`

`src/mail/client.py` là dispatcher — route theo `box.provider`, expose public API duy nhất cho bên ngoài.

### Tầng 2 — Service Registrars (bên dùng mail) `src/services/`

Đăng ký tài khoản ở các dịch vụ AI/SaaS. Tiêu thụ Inbox Providers để nhận email xác minh.

| Directory | Domain | Registry key |
|-----------|--------|-------------|
| `openrouter_ai/` | openrouter.ai | `OPENROUTER` |
| `chatgpt_com/` | chatgpt.com | `CHATGPT` |
| `elevenlabs_io/` | elevenlabs.io | `ELEVENLABS` |
| `leonardo_ai/` | leonardo.ai | `LEONARDO` |
| `klingai_com/` | klingai.com | `KLINGAI` |
| `proton_me/` | proton.me | `PROTON` |
| `artificialanalysis_ai/` | artificialanalysis.ai | `ARTIFICIALANALYSIS` |
| `testmail_app/` | testmail.app | `TESTMAIL` |

### testmail.app — Dual-role service

testmail.app đóng 2 vai trò đồng thời:
- **Inbox Provider** (`src/mail/providers/testmail_app.py`) — nhận email xác minh cho các service khác
- **Service Registrar** (`src/services/testmail_app/registrar.py`) — đăng ký account để lấy namespace + API key

Khi cần thêm namespace mới: chạy `src/services/testmail_app/registrar.py`, credential được ghi vào `config/mail.yaml`.

---

## Naming Convention

### Directories (Python packages)

Dùng `_` thay `.` cho TLD vì Python không cho phép `.` trong package name:
```
openrouter_ai/   # openrouter.ai
chatgpt_com/     # chatgpt.com
elevenlabs_io/   # elevenlabs.io
```

### Config YAML keys

Dùng `.` đầy đủ:
```yaml
# config/chatgpt.yaml, config/elevenlabs.yaml, v.v.
# KHÔNG có mail provider trong YAML — lấy từ SQLite DB
service:
  signup_url: "https://auth.openai.com/create-account"
  timeout_sec: 60
  max_retries: 5
```

Mail providers được quản lý trong DB (`data/accounts.db`), không phải YAML:
```
testmail.app  → tags=["any"]         # serve mọi service
mail.tm       → tags=["elevenlabs"]  # chỉ serve elevenlabs
```

### Registry keys (Python internal)

UPPERCASE, không cần TLD — đây là internal enum-like identifiers:
```python
_FACTORIES = {
    "OPENROUTER": _make_openrouter,   # không phải display name
    "CHATGPT":    _make_chatgpt,
    ...
}
```

---

## Design Patterns

### 1. Strategy Pattern — `make_registrar`

```
Registrar Protocol (FP)
├── register_openrouter (FP)
├── register_elevenlabs (FP)
├── register_chatgpt (FP)
└── ...
```

Tất cả registrar là pure async function `(cfg, log_fn, save_fn) → Optional[AccountRecord]`.
`registry.py` thống nhất qua `_FACTORIES` dict → caller chỉ gọi `registrar(log_fn, save_fn)`.

```python
registrar = make_registrar("OPENROUTER", cfg)
record = await registrar(log_fn, save_fn)
```

### 2. Repository Pattern — `database.py`

Persistence logic tập trung trong pure functions — không có OOP Repository class:

```python
# src/core/database.py
insert_account(db_path, record)               # INSERT, skip duplicate
upsert_account(db_path, record)               # INSERT OR REPLACE
get_accounts(db_path, service, ...)           # query với filter
update_account(db_path, service, email, ...)  # PATCH fields
delete_account(db_path, service, email)       # DELETE
```

Tất cả hàm nhận `db_path` như parameter — không có global state, dễ test.

### 3. Dispatcher Pattern — `mail/client.py`

```python
async def get_messages(box: Mailbox) -> List[Dict]:
    match box.provider:
        case "testmail.app":   return await testmail_app.get_messages(box)
        case _:                return await mail_tm.get_messages(box)
```

---

## Functional Programming

- **Pure functions**: `generate_password()`, `_testmail_parts()`, `_pick_weekly_window()`, `format_row()` — no side effects
- **Immutable config**: Tất cả config là `@dataclass(frozen=True)`
- **Stateless helpers**: State được pass qua parameters, không có global mutable state trong business logic
- **`asyncio.gather`** thay `ThreadPoolExecutor` — non-blocking concurrency

---

## SOLID Principles

| Principle | Áp dụng |
|---|---|
| **S** — Single Responsibility | `logger.py` chỉ log, `database.py` chỉ persist, `mail/providers/*` mỗi file 1 provider |
| **O** — Open/Closed | Thêm inbox provider mới: tạo file trong `mail/providers/`, đăng ký trong `client.py` dispatcher; thêm provider keys vào DB |
| **L** — Liskov Substitution | Tất cả registrar functions có cùng signature `(cfg, log_fn, save_fn) → Optional[AccountRecord]` |
| **I** — Interface Segregation | Mỗi provider module export đúng 4 async functions: create, get, body, wait |
| **D** — Dependency Inversion | Registrars phụ thuộc vào abstractions (`AppConfig`, `Mailbox`) không phải concrete I/O |

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│  Tauri + React UI  (ui/)                            │
│  Vite dev server / Tauri WebView                    │
└───────────────────────┬─────────────────────────────┘
                        │  HTTP  (127.0.0.1:8799)
┌───────────────────────▼─────────────────────────────┐
│  FastAPI server  (src/api/)  — run_api.py            │
│  GET /providers, PUT /providers/{type}/tags          │
│  GET /accounts/{service}, POST /accounts/run         │
└───────────┬───────────────────────┬─────────────────┘
            │                       │
┌───────────▼──────────┐  ┌─────────▼────────────────┐
│  src/core/database.py │  │  src/services/registry.py │
│  SQLite accounts.db   │  │  make_registrar(svc, cfg) │
│  accounts table       │  └──────────┬───────────────┘
│  mail_providers table │             │
│  provider_tags table  │  ┌──────────▼──────────────────────┐
└──────────────────────┘  │  Service Registrars (FP)         │
                           │  register_elevenlabs(cfg,log,save)│
                           │  register_openrouter(cfg,log,save)│
                           │  register_chatgpt(cfg,log,save)  │
                           └──────────┬──────────────────────┘
                                      │
                           ┌──────────▼──────────────────────┐
                           │  src/mail/client.py              │
                           │  create_mailbox(providers, cfg)  │
                           │  Circuit breaker + failover      │
                           └──────────┬──────────────────────┘
                                      │
               ┌──────────────────────┼────────────────────┐
               ▼                      ▼                     ▼
        mail_tm.py           testmail_app.py
```

## Dependency Graph

```
main.py / run_api.py
 └─ load_config()              ← src/config/settings.py
 └─ init_db()                  ← src/core/database.py (SQLite)
 │
 ├─ FastAPI routers             ← src/api/routers/
 │   ├─ GET /providers          → get_provider_domains(db_path)
 │   ├─ PUT /providers/{d}/tags → set_provider_domain_tags(db_path, ...)
 │   └─ POST /accounts/run      → make_registrar() → registrar()
 │
 ├─ register_elevenlabs (FP)   ← src/services/elevenlabs_io/registrar.py
 │   ├─ create_mailbox()        ← src/mail/client.py
 │   ├─ create_browser()        ← src/core/browser.py
 │   ├─ solve_hcaptcha()        ← src/services/elevenlabs_io/captcha.py
 │   ├─ handle_onboarding()     ← src/services/elevenlabs_io/onboarding.py
 │   └─ create_api_key()        ← src/services/elevenlabs_io/api_key.py
 │
 ├─ register_chatgpt (FP)      ← src/services/chatgpt_com/registrar.py
 │   ├─ create_mailbox()        ← src/mail/client.py
 │   ├─ create_browser()        ← src/core/browser.py
 │   └─ _SharedCallbackServer   ← src/services/chatgpt_com/oauth_server.py
 │
 ├─ register_openrouter (FP)   ← src/services/openrouter_ai/registrar.py
 │   └─ create_mailbox()        ← src/mail/client.py
 │
 └─ register_artificialanalysis (FP) ← src/services/artificialanalysis_ai/registrar.py
     └─ create_mailbox()        ← src/mail/client.py
```

---

## Data Flow — ElevenLabs

```
1. cfg.mail.providers_for("elevenlabs")
        ↓ ("testmail.app:ns:key", ...)  ← từ SQLite DB
2. create_mailbox(providers, cfg.mail_cfg)
        ↓ Mailbox(email, token, ...)
3. generate_password(14)
        ↓ password
4. Playwright: goto signup_url → fill form → click Sign Up
        ↓
5. solve_hcaptcha(page, logger, cfg)
        ↓ bool (True = solved)
6. _wait_for_dashboard() loop:
        ├── verification email? → wait_for_message(box, ...) → goto verify link
        ├── sign-in page?       → fill credentials → submit
        ├── onboarding?         → handle_onboarding()
        └── dashboard?          → break
7. create_api_key(page, logger, cfg)
        ↓ "sk_..."
8. save_fn(AccountRecord)
        ↓ upsert_account(db_path, record)
        ↓ SQLite: accounts table
```

---

## Config Loading

```
config.yaml (YAML file)
      ↓ yaml.safe_load()
raw dict
      ↓ _parse_section(cls, raw)
frozen dataclasses:
  AppConfig
  ├── TimeoutConfig
  ├── LLMConfig
  ├── CaptchaConfig
  └── ElevenLabsConfig
```

`_parse_section` chỉ pass keys mà dataclass định nghĩa — keys thừa trong YAML bị bỏ qua, keys thiếu dùng default.

---

## Anti-detection

Browser được tạo với:
- Custom User-Agent: `Chrome/120.0.0.0`
- Viewport: `1280×720`
- Init script: `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`

Điều này giúp tránh bot detection của các trang web.

---

## Browser Gateway — host delegates browser work

**Vấn đề:** container `registrar` không có binary `camoufox` (anti-detect browser, Windows-only, cài trên host). Một số service (Cloudflare, AA re-login) cần camoufox để bypass Turnstile/bot-detection.

**Giải pháp:** Browser Gateway — process Python chạy trên **host** (`tools/host_browser_agent.py`, `127.0.0.1:9999`). Nó mở camoufox + chạy task automation. Container gọi qua HTTP.

```
container (registrar)                    host (Browser Gateway)
─────────────────────                    ──────────────────────
register_cloudflare()                    host_browser_agent.py:9999
  └─ run_browser_task("register_cloudflare")  ──HTTP──>  /v1/tasks
     (common.browser_gateway_client)                  │
                                                       ↓
                                                  open_browser(camoufox)
                                                  register_cloudflare task
                                                  (src/api/tools/browser_tasks/)
                                                       │
                                                       ↓
                                                  _signup_flow() → record dict
                                                       │
                                  <──result JSON──     └─ return
  save_fn(record) → DB
```

### Thêm service mới cần camoufox

1. **Task handler** — tạo `src/api/tools/browser_tasks/<name>.py`:
   ```python
   @register("<task_name>", engine="camoufox")  # headless đọc từ cfg.browser.headless
   async def task_name(*, browser: Browser, args: dict, log_fn=None) -> dict:
       # browser do gateway mở + truyền vào. KHÔNG mở browser trực tiếp.
       ctx = await browser.new_context()
       try:
           page = await ctx.new_page()
           record = await _flow(page, args, cfg, log_fn or (lambda m: None))
       finally:
           await ctx.close()
       return {"email": record.email, "api_key": record.api_key, ...}
   ```
2. **Import side-effect** — thêm `from . import <name>` vào `browser_tasks/__init__.py` (trigger `@register`).
3. **Service entrypoint gọi gateway** — trong `src/services/<svc>/registrar.py`:
   ```python
   from common.browser_gateway_client import run_browser_task
   result = await run_browser_task(cfg.api.host_browser_agent_url, "<task_name>", args={}, log_fn=log_fn)
   await save_fn(AccountRecord(..., **result))
   ```
4. **Cấm** mở browser trực tiếp trong container (`create_browser()` camoufox) — sẽ fail vì không có binary.

### Task `add_cf_to_9router` — auto-add CF account vào service ngoài

Sau khi `register_cloudflare` lưu DB, `_add_to_9router` gọi task `add_cf_to_9router` để add account vào **9Router** (`localhost:20128`) — service riêng, tao chỉ dùng (không quản lý code). Task mở fresh context camoufox, goto dashboard, **login nếu rơi `/login`** (1 nhánh `if`, không fallback — pass `@Anhtuan13` từ `cfg.ninerouter.password`), mở form Add, điền Name=email + API Key + Account ID, click **Check** (9Router verify token qua CF API), đợi badge Valid/Invalid, Save nếu valid. Invalid → `_add_to_9router` set `check_status="invalid"` trên base table (`update_account_async`, DB-only field — `AccountRecord` không có).

DOM đã verify qua Playwright (login page, Add button, panel scope qua `<h2>`, badge `<span>` leaf Valid/Invalid). Chi tiết trong file task.

### Debug flow khi selector sai

Khi UI target là React SPA (render sau `domcontentloaded`), dump DOM thật trước khi code selector — **không đoán** (xem CLAUDE.md quy trình bắt buộc):

1. Tạo **task dump tạm** trong `browser_tasks/` (đăng ký `@register`, import trong `__init__.py`).
2. Trigger qua `POST /v1/tasks` (`curl` hoặc container). Task chạy full flow đến bước fail, dump `main.innerHTML` + list element cần thiết.
3. Phân tích DOM → code selector đúng → xóa task dump.

**Lưu ý Base UI / Radix checkbox:** control ẩn (`<input type=checkbox>` clip-path, position fixed) không `.check()` được (ngoài viewport). Click `<label>`/span bị accordion overlay intercept. **Toggle chuẩn = `focus()` + `press("Space")`** trên `<span role=checkbox tabindex=0>` — keyboard interaction, không bị pointer overlay chặn.


---

## Error Handling

Mỗi registrar có try/except bao toàn bộ flow:
- Log lỗi
- Screenshot → `screenshots/elevenlabs_error.png`
- `traceback.print_exc()` để debug
- Return `None` (caller quyết định tiếp theo)
