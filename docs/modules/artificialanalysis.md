# Artificial Analysis Service (`src/services/artificialanalysis/`)

Tự động tạo tài khoản artificialanalysis.ai và lấy API key:
**temp email → magic link (không password, không captcha) → tạo API key**

---

## Tổng quan flow

```
register_artificialanalysis(cfg, log_fn, save_fn)
  │
  ├─ [1/5] goto https://artificialanalysis.ai/login
  ├─ [2/5] fill email → click "Continue" (gửi magic link)
  ├─ [3/5] poll temp mail → extract magic link URL
  ├─ [4/5] navigate magic link → handle JSON token → /orgs → extract org slug
  └─ [5/5] goto /orgs/{slug}/api-access → Create API key → extract aa_...
```

---

## Đặc điểm quan trọng của artificialanalysis.ai

### Login page (`/login`)

- **Không dùng password** — magic link qua email, không OTP.
- Trang dùng **Next.js** + **React**, DOM render client-side nên KHÔNG thể dùng
  `requests.get()` → BẮT BUỘC Playwright.
- Các button trên trang login:
  1. **`Continue with Google`** — OAuth ← **PHẢI TRÁNH**
  2. **`Continue`** (type=submit) — gửi magic link ← **DÙNG CÁI NÀY**
- Locator: `page.locator("button[type='submit']:has-text('Continue')")`
  — dùng `type='submit'` để tránh match Google OAuth button.

### Magic link email

- Sender: `mail@mail.artificialanalysis.ai`
- Body chứa link dạng: `https://artificialanalysis.ai/api/auth/verify?token=...`
- Extract bằng `extract_link(body, "artificialanalysis")`.
- Link verify trả về JSON `{"token": "..."}` → cần navigate thêm đến `/orgs`.

### Post-login redirect

- Sau verify, navigate đến `/orgs` → tự redirect sang `/orgs/{slug}/insights`.
- Extract org slug từ URL: `re.search(r"/orgs/([^/]+)", final_url)`.
- Nếu vẫn ở `/login` → auth thất bại.

### API Access page (`/orgs/{slug}/api-access`)

- Button **"Create API key"** mở dialog.
- Dialog chứa `form#new-api-key-form` với input tên key.
- Submit bằng `page.locator("button[type='submit'][form='new-api-key-form']").click()`.
- Key format: `aa_{alphanumeric 10+}`.
- Extract bằng JS evaluate tìm pattern `aa_[a-zA-Z0-9_-]{10,}` trong body + input/textarea/code.

---

## Architecture: Functional Programming

Module này dùng **FP pattern** (không OOP/BaseRegistrar):

- **Public function**: `register_artificialanalysis(cfg, log_fn, save_fn) → Optional[AccountRecord]`
- **Step helpers**: `_fill_email_and_submit()`, `_fetch_magic_link()`, `_navigate_magic_link()`, `_create_api_key()`
- Match `Registrar` protocol qua `partial(register_artificialanalysis, cfg)` trong registry.
- Không fallback, không retry loop bên trong step — retry ở top-level với email mới.

---

## Temp mail

- Provider: `mail.tm` (config trong `mail.yaml` → `per_service.artificialanalysis`).
- Artificial Analysis chấp nhận domain `dollicons.com` (mail.tm).

---

## Config

File: `config/artificialanalysis.yaml`

| Key | Default | Mô tả |
|---|---|---|
| `login_url` | `https://artificialanalysis.ai/login` | Trang login |
| `app_url_contains` | `artificialanalysis.ai` | Detect app URL |
| `magic_link_wait_sec` | `120` | Thời gian chờ magic link email (giây) |
| `post_submit_wait_ms` | `3000` | Chờ sau khi submit email (ms) |

---

## Files

| File | Trách nhiệm |
|---|---|
| `registrar.py` | Flow chính: temp mail → login → magic link → API key |
| `__init__.py` | Package init |

---

## Entry point

```bash
python run_artificialanalysis.py   # tạo 1 tài khoản
```

---

## API key header

Artificial Analysis data API dùng header `x-api-key` (KHÔNG phải `Authorization: Bearer`):

```
x-api-key: aa_xxxxx
```
