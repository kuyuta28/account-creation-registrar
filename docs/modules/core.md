# Core Modules (`src/core/`)

Các module nền tảng — không phụ thuộc vào service cụ thể nào, dùng chung cho tất cả.

---

## `browser.py` — Browser Factory

**Nhiệm vụ**: Khởi tạo Playwright browser/context/page với cấu hình chuẩn.

### Functions

#### `create_browser(playwright, cfg) → Browser`

Mở Chromium với chế độ headless theo config.

```python
browser = create_browser(playwright, cfg)
# cfg.headless = False → mở browser window (với --start-minimized — không hiện lên foreground)
# cfg.headless = True  → chạy ẩn (không thấy UI)
```

Khi `headless=False`, hàm tự động pass `--start-minimized` vào Chromium args — browser mở ở taskbar, không bật lên che cửa sổ đang active.

```python
def create_browser(playwright, cfg) -> Browser:
    args = ["--start-minimized"] if not cfg.headless else []
    return playwright.chromium.launch(headless=cfg.headless, args=args)
```

#### `create_context(browser) → BrowserContext`

Tạo context với:
- **User-Agent**: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0`
- **Viewport**: `1280×720`

#### `create_page(context) → Page`

Tạo page và inject anti-detection script:
```javascript
Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
```

Giúp tránh bot detection bằng cách ẩn dấu hiệu automation.

### Hằng số nội bộ

| Hằng | Giá trị |
|---|---|
| `_USER_AGENT` | `Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36` |
| `_VIEWPORT` | `{"width": 1280, "height": 720}` |
| `_ANTI_DETECT` | JS ẩn `navigator.webdriver` |

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
    service: str      # "ELEVENLABS" | "PROTON"
    email: str
    password: str
    api_key: str = "" # optional, dùng cho ElevenLabs
```

#### `to_json_entry() → dict`

Serialize để lưu vào JSON. Loại bỏ `service`, bỏ `api_key` nếu rỗng.

```python
AccountRecord("ELEVENLABS", "a@b.com", "pw", "sk_abc").to_json_entry()
# → {"email": "a@b.com", "password": "pw", "api_key": "sk_abc"}

AccountRecord("PROTON", "a@b.com", "pw").to_json_entry()
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
| Proton | `proton_accounts.json` |

Format:
```json
[
  {"email": "abc@domain.com", "password": "P@ssword1", "api_key": "sk_abc123..."},
  {"email": "xyz@domain.com", "password": "P@ssword2", "api_key": "sk_xyz456..."}
]
```
