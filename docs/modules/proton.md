# Proton Service (`src/services/proton/`)

Tự động tạo tài khoản Proton Mail miễn phí.

> **Lưu ý**: Proton dùng captcha riêng (không phải hCaptcha) — hiện tại cần giải **thủ công** trong browser window.

---

## Flow

```
ProtonRegistrar.register()
  │
  ├─ [1/6] goto https://account.proton.me/signup?plan=free
  ├─ [2/6] fill username (trong iframe) + retry nếu bị taken
  ├─ [3/6] fill password + confirm password
  ├─ [4/6] click Submit
  ├─ ── Lưu account ngay lập tức (trước captcha để không mất credentials) ──
  ├─ [5/6] HIỂN THỊ BROWSER → user giải captcha thủ công
  └─ [6/6] chờ redirect đến /mail dashboard
```

---

## `registrar.py` — ProtonRegistrar

### Class `ProtonRegistrar(BaseRegistrar)`

```python
registrar = ProtonRegistrar(cfg, logger, repo)
record = registrar.register()
```

#### Constructor

```python
def __init__(self, cfg: AppConfig, logger: Logger, repo: AccountRepository)
```

#### `register() → Optional[AccountRecord]`

1. Generate username (`generate_username(17)`) và password (`generate_password(15)`)
2. Mở Playwright browser
3. Gọi `_run()` — thực hiện flow
4. Nếu thành công: `repo.save(record)`
5. Nếu exception: log + screenshot + traceback

#### `_run(page, username, password) → Optional[AccountRecord]`

**Step 1**: `page.goto("https://account.proton.me/signup?plan=free")`

**Step 2**: Fill username trong iframe
```python
frame = _find_signup_iframe(page)   # tìm signup iframe
_fill_username(frame, username)     # fill + kiểm tra available
# Nếu taken → retry tối đa 5 lần với username mới
```

**Step 3**: Fill password
```python
page.locator("#password").fill(password)
page.locator("#password-confirm").fill(password)
```

**Step 4**: Submit
```python
# Thử selector theo thứ tự:
#   1. button[type="submit"]
#   2. get_by_text("Create account")
```

**Lưu ngay lập tức** trước khi captcha:
```python
record = AccountRecord(service="PROTON", email=f"{username}@protonmail.com", password=password)
self._repo.save(record)
```
> Lý do lưu trước: nếu user đóng browser hoặc captcha lỗi, credentials không bị mất.

**Step 5**: Hiện thông báo "Solve CAPTCHA in browser!" — user giải thủ công.

**Step 6**: `_wait_for_inbox(page)` — poll cho đến khi URL chứa `"mail"`.

#### `_wait_for_inbox(page)`

Loop tối đa `(email_wait * 1000) // nav_delay` iterations:
```python
for _ in range(max_polls):
    page.wait_for_timeout(self._cfg.timeouts.nav_delay)
    _dismiss_popups(page)
    if "mail" in url and ("inbox" in url or "all-mail" in url):
        return
```

---

## Private Helpers

### `_find_signup_iframe(page) → Optional[Frame]`

Tìm iframe signup của Proton (form username nằm trong iframe riêng):
```python
page.wait_for_selector("iframe", state="attached", timeout=30_000)
for frame in page.frames:
    if "Name=email" in frame.url or frame.locator("#username").count() > 0:
        return frame
return None
```

### `_fill_username(frame, username) → bool`

Inject username qua React-compatible approach (set value + dispatch input event):
```python
frame.evaluate(f"""() => {{
    const input = document.querySelector('#username');
    if (input) {{
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        setter.call(input, '{username}');
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
}}""")
```
Return `True` nếu available, `False` nếu taken.

### `_dismiss_popups(page)`

Click các button popup ("Skip", "Maybe later", "No, thanks", "Not now") nếu xuất hiện.

---

## Lưu trữ

File: `proton_accounts.json`

```json
[
  {"email": "username@protonmail.com", "password": "P@ssw0rd123456"}
]
```

Không có `api_key` (Proton không có API key trong flow này).

---

## Khác biệt so với ElevenLabs

| | ElevenLabs | Proton |
|---|---|---|
| Captcha | **Auto** (LLM vision) | **Thủ công** (user giải) |
| Email verify | Temp email → link click | Không cần |
| Lưu account | Sau khi hoàn thành | **Trước captcha** (để không mất data) |
| API key | Có (`sk_...`) | Không |
| Dashboard detect | URL pattern | URL chứa `"mail"` |
