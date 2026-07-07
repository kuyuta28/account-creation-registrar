# Core Modules (`src/core/`)

Các module nền tảng — không phụ thuộc vào service cụ thể nào, dùng chung cho tất cả.

---

## Browser Gateway (không còn `core/browser.py`)

Toàn bộ browser automation chạy trên **host** qua Browser Gateway — container
`registrar` không mở browser trực tiếp (không có camoufox binary trong image).

- **Agent host**: `registrar/tools/host_browser_agent.py` (`127.0.0.1:9999`).
- **Task registry**: `src/api/tools/browser_tasks/` — mỗi task là
  `@register("task_name", engine="camoufox")` handler `(*, browser, args, log_fn) -> dict`.
- **Container client**: `common.browser_gateway_client.run_browser_task(
  gateway_url, task, args, *, headless=None, on_log=None) -> dict`.
- **Engine abstraction**: `src/api/tools/browser_gateway_engines.py` —
  `open_browser(engine, headless, proxy)` (camoufox | edge | chromium).

`cfg.headless` (top-level, KHÔNG phải `cfg.browser.headless`) контроль headless.
Service registrar delegate sang gateway task; `_signup_flow`/flow helpers là pure
automation nhận `page`/`context` từ gateway task wrapper.

Xem `docs/architecture.md` → "Browser Gateway" + `docs/PLAN-GATEWAY-MIGRATION.md`.

---

## `logger.py` — Logger

**Nhiệm vụ**: In ra stdout và ghi vào file log đồng thời.

### Class `Logger`

#### `__init__(log_file: Path, append: bool = False)`

- Tạo thư mục `debug/` nếu chưa có
- `append=False`: xóa file log cũ khi khởi động
- `append=True`: giữ lại log cũ, ghi tiếp

#### `log(msg: str) → None`

In ra stdout và append vào file log với timestamp:
```
[14:32:05] [captcha] Round 1/10 | challenge: x=381 y=76 520×570px
```

#### `dump_html(page: Page, name: str) → None`

Lưu HTML của page hiện tại vào `debug/<name>`.  
Dùng để debug khi flow bị stuck.

```python
logger.dump_html(page, "apikey_page.html")
# → debug/apikey_page.html
```

#### `screenshot(page: Page, name: str, screenshot_dir: Path) → None`

Chụp screenshot vào `screenshots/<name>`.  
Thường dùng khi có exception để debug.

```python
logger.screenshot(page, "elevenlabs_error.png", cfg.screenshot_dir)
# → screenshots/elevenlabs_error.png
```

---

## `password.py` — Credential Generator

**Nhiệm vụ**: Tạo password và username ngẫu nhiên. Pure functions — không I/O.

### `generate_password(length: int = 14) → str`

Tạo password đảm bảo:
- Ít nhất 1 ký tự hoa
- Ít nhất 1 ký tự thường
- Ít nhất 1 chữ số
- Ít nhất 1 ký tự đặc biệt `@`
- Độ dài chính xác theo `length`

```python
generate_password(14)  # "4fJS@hZa0ooRda"
generate_password(8)   # "A2@bcd3e"
```

### `generate_username(length: int = 17) → str`

Tạo username:
- Bắt đầu bằng chữ cái thường
- Còn lại: chữ thường + số
- Độ dài chính xác theo `length`

```python
generate_username(17)  # "am7sqsk5wz3kl9p2q"
```

---

## `storage.py` — Account Persistence

**Nhiệm vụ**: Đọc/ghi account records. Repository pattern.

### `AccountRecord` (frozen dataclass)

```python
@dataclass(frozen=True)
class AccountRecord:
    service: str      # "ELEVENLABS" | "LEONARDO" | ...
    email: str
    password: str
    api_key: str = "" # optional, dùng cho ElevenLabs
```

#### `to_json_entry() → dict`

Serialize để lưu vào JSON. Loại bỏ `service`, bỏ `api_key` nếu rỗng.

```python
AccountRecord("ELEVENLABS", "a@b.com", "pw", "sk_abc").to_json_entry()
# → {"email": "a@b.com", "password": "pw", "api_key": "sk_abc"}

AccountRecord("LEONARDO", "a@b.com", "pw").to_json_entry()
# → {"email": "a@b.com", "password": "pw"}
```

### `AccountRepository`

#### `__init__(base_dir: Path)`

Tất cả file được lưu trong `base_dir`.

#### `save(record: AccountRecord) → None`

Append record vào `<base_dir>/<service_lower>_accounts.json`.

```python
repo.save(AccountRecord("ELEVENLABS", "x@y.com", "P@1", "sk_xyz"))
# Ghi vào: elevenlabs_accounts.json
```

File JSON có dạng array — nếu file chưa tồn tại thì tạo mới.

#### `all(service: str) → List[dict]`

Đọc tất cả records của service từ JSON file.

```python
repo.all("elevenlabs")
# → [{"email": ..., "password": ..., "api_key": ...}, ...]
```

### File lưu trữ

| Service | File |
|---|---|
| ElevenLabs | `elevenlabs_accounts.json` |

Format:
```json
[
  {"email": "abc@domain.com", "password": "P@ssword1", "api_key": "sk_abc123..."},
  {"email": "xyz@domain.com", "password": "P@ssword2", "api_key": "sk_xyz456..."}
]
```
