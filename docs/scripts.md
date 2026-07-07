# CLI Scripts

---

## `main.py` — Menu chính

```powershell
python main.py
```

Hiển thị menu chọn dịch vụ:
```
============================================================
  ACCOUNT CREATION AUTOMATION
============================================================
  [1] ElevenLabs + API key
  [2] Leonardo AI
  [5] Check ElevenLabs API key status
  [6] Check ChatGPT account status
  [7] Check ChatGPT quota (weekly usage%)
  [8] Sync exported auth files
  [0] Exit
============================================================
Choose:
```

**Thiết kế**:
- `_build_menu()` registry: dict `key → (label, registrar_instance)`
- Thêm service mới = thêm 1 dòng trong `_build_menu()`, không sửa gì khác
- `load_config()` → `Logger` → `AccountRepository` → inject vào registrar

**Output khi thành công**:
```
============================================================
✅ ACCOUNT CREATED SUCCESSFULLY!
============================================================
  Email:    abc@domain.com
  Password: P@ssword123456
  API Key:  sk_570c7e906...
============================================================
```

---

## `run_elevenlabs.py` — ElevenLabs trực tiếp

```powershell
python run_elevenlabs.py
```

Tạo tài khoản ElevenLabs không qua menu — dùng khi muốn chạy nhanh hoặc trong script.

**Tương đương** với chọn `[2]` trong `main.py` nhưng không có menu overhead.  
Luôn gọi `registrar.cleanup()` trong `finally` block để đảm bảo browser được đóng dù có lỗi.

**Output**:
```
============================================================
  ElevenLabs Account Creator
============================================================
[1/5] Opening ElevenLabs signup...
[2/5] Filling form...
  ✓ Clicked Sign Up
  ⏳ Waiting 4000ms for captcha to load...
[3/5] 🧩 Auto-solving CAPTCHA with LLM vision...
  model=gpt-5.4  max_rounds=10
  [captcha] Inline challenge detected: x=381 y=76 520×570px
  [captcha] Round 1/10 | ...
  [captcha] ✅ Challenge gone — passed!
[4/5] 📧 Verification email detected...
[5/5] Creating API key...
  ✅ API key: sk_570c7e906...
💾 Saved to elevenlabs_accounts.json

============================================================
✅ DONE!
============================================================
  Email:    abc@domain.com
  Password: P@ssword123456
  API Key:  sk_570c7e906abc123...
============================================================
```

---

## `run_chatgpt.py` — ChatGPT trực tiếp

```powershell
python run_chatgpt.py
python run_chatgpt.py 3
```

Tạo tài khoản ChatGPT trực tiếp bằng flow OAuth PKCE.

---

## `run_leonardo.py` — Leonardo AI trực tiếp

```powershell
python run_leonardo.py
python run_leonardo.py 3
```

Tạo tài khoản Leonardo AI trực tiếp bằng email flow.
Bước Cloudflare Turnstile hiện là bước thủ công trong browser, sau đó script sẽ tự
poll email xác thực và đi tiếp.

---

## `check_keys.py` — Kiểm tra API keys

```powershell
python check_keys.py
```

Đọc tất cả accounts từ `elevenlabs_accounts.json`, gọi ElevenLabs API kiểm tra từng key.

**Output**:
```
Checking 4 account(s)...

Email                               Valid  Status     Used    Limit  Remaining   Resets
----------------------------------------------------------------------------------------------------------
am7sqsk5wz@dollicons.com            ✅     active      1,234  10,000      8,766  2026-04-01
rkc8nmamk4@dollicons.com            ✅     active          0  10,000     10,000  2026-04-01
itn13hi6du@dollicons.com            ❌     invalid key (401)
1ldyipco0j@dollicons.com            ✅     active        500  10,000      9,500  2026-04-01
```

**API endpoint**: `GET https://api.elevenlabs.io/v1/user`  
**Header**: `xi-api-key: <key>`

### `check_key(api_key: str) → dict`

Pure function — kiểm tra 1 key:

```python
# Key hợp lệ:
{
    "valid": True,
    "tier": "free",
    "status": "active",
    "characters_used": 1234,
    "characters_limit": 10000,
    "characters_remaining": 8766,
    "resets_on": "2026-04-01"
}

# Key không hợp lệ:
{"valid": False, "reason": "invalid key (401)"}
{"valid": False, "reason": "empty key"}
{"valid": False, "reason": "HTTP 500"}
```

---

## `debug_captcha.py`

Script debug độc lập cho captcha solver (không liên quan đến registration flow).  
Mở ElevenLabs signup, điền form dummy, trigger captcha, chạy `solve_hcaptcha()` thật từ module captcha.

```powershell
python debug_captcha.py
```

- Dùng `config.yaml` cho tất cả settings (không hardcode LLM URL/model/email)
- Dùng `create_browser/context/page` từ `src/core/browser.py`
- Sau khi solve xong, chờ user nhấn Enter rồi mới đóng browser

---

## Log files

| File | Mô tả |
|---|---|
| `debug/run.log` | Log toàn bộ session, có timestamp. Bị xóa mỗi lần chạy (nếu `log.append: false`) |
| `debug/*.html` | HTML dump của các trang quan trọng để debug |
| `debug/captcha_roundNN.png` | Screenshot captcha widget mỗi round |
| `screenshots/elevenlabs_error.png` | Chụp khi ElevenLabs flow bị exception |

---

## Data files

| File | Dịch vụ | Format |
|---|---|---|
| `elevenlabs_accounts.json` | ElevenLabs | `[{email, password, api_key}, ...]` |
