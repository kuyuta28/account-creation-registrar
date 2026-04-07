# 2slides Service (`src/services/twoslides/`)

Tự động tạo tài khoản 2slides.com và lấy API key:
**temp email → login (OTP, không cần password) → tạo API key**

---

## Tổng quan flow

```
TwoSlidesRegistrar.register()
  │
  ├─ [1/4] goto https://2slides.com/login
  ├─ [2/4] fill email → click "Send" (gửi OTP)
  ├─ [3/4] poll temp mail → extract 6-digit OTP → fill OTP → click "Continue →"
  └─ [4/4] goto /api → click tab "API Keys" → create key → extract sk-2slides-...
```

---

## Đặc điểm quan trọng của 2slides.com

### Login page (`/login`)

- **Không dùng password** — chỉ OTP qua email.
- Trang dùng **Next.js** + **React**, DOM render client-side nên KHÔNG thể dùng
  `requests.get()` để phân tích — BẮT BUỘC phải dùng Playwright.
- Có **4 button** trên trang login:
  1. (empty) — hamburger menu
  2. `English EN` — language picker
  3. **`Continue with Google`** — OAuth Google redirect ← **PHẢI TRÁNH**
  4. **`Send`** — gửi OTP email ← **DÙNG CÁI NÀY**
  5. **`Continue →`** — submit OTP ← **DÙNG SAU KHI ĐIỀN OTP**

- **`Continue with Google` nằm TRƯỚC `Send` trong DOM** → nếu dùng
  `get_by_role("button", name="Continue")` sẽ match nhầm vào Google OAuth.
- **PHẢI** dùng JS evaluate tìm chính xác text `send` hoặc `continue →`,
  skip bất kỳ button nào có chữ `google`.

### API page (`/api`)

- Dùng **Radix UI tabs**: `API Endpoints`, `MCP Server`, `API Keys`, `API Playground`.
- Tab mặc định là `API Endpoints` — **PHẢI click vào tab `API Keys` trước**.
- Click tab bằng `page.locator('[role="tab"]').filter(has_text="API Keys").click()`
  — dùng Playwright locator, KHÔNG dùng JS evaluate (React state không update).
- Sau khi tab active, button `Create Key` mới xuất hiện trong tab panel.
- Dialog tạo key:
  1. Input "Key name" → fill bất kỳ text
  2. Button "Create" → confirm
  3. Key `sk-2slides-{64 hex chars}` hiển thị trong dialog → extract bằng regex.

### Email OTP

- Sender: `service@2slides.com`
- Subject pattern: `2Slides Login Verification Code: XXXXXX`
- OTP: 6 chữ số, extract bằng `\b(\d{6})\b`

---

## Temp mail domain

- `mail.tm` hiện chỉ có domain `dollicons.com` — **2slides chấp nhận** domain này.
- `mail.gw` hay bị 502 — code có fallback tự động giữa 2 provider.
- Config ưu tiên: `mail.gw` trước, fallback `mail.tm`.

---

## Files

| File | Trách nhiệm |
|---|---|
| `registrar.py` | Flow chính: temp mail → login → OTP → API key |
| `api_key.py` | Switch tab API Keys → tạo key → extract `sk-2slides-...` |

---

## Entry point

```bash
python run_2slides.py          # tạo 1 tài khoản
python run_2slides.py 5        # tạo 5 tài khoản
```

---

## Browser reuse

- Browser + context + page tạo **MỘT LẦN** lúc đầu.
- Giữa các acc chỉ `clear_cookies()` — browser cửa sổ KHÔNG đóng/mở lại.
- Khác với các service khác (ElevenLabs, Leonardo) tạo context mới mỗi acc —
  2slides đơn giản hơn (chỉ OTP, không password) nên reuse page an toàn.

---

## Quy trình debug khi viết service mới

**BẮT BUỘC phải làm trước khi code:**

1. **Dùng Playwright mở trang target**, dump HTML rendered (`page.content()`).
   KHÔNG dùng `requests.get()` — nhiều trang render client-side.
2. **Phân tích HTML dump** — liệt kê tất cả `<button>`, `<input>`, tab, form.
   Xác định chính xác button nào cần click, input nào cần fill.
3. **Xác định thứ tự click** — nhiều trang có button tên giống nhau hoặc
   button OAuth nằm trước button mong muốn trong DOM.
4. **Dump HTML sau mỗi action** (`logger.dump_html()`) — verify DOM thay đổi
   đúng mong đợi.
5. **Chỉ code sau khi hiểu rõ DOM** — không đoán, không giả định.
