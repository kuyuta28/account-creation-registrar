# NopeCHA — Captcha Solver Research

> **Trạng thái:** Research ghi nhận cho tương lai. Chưa tích hợp.

## Tổng quan

- **Repo:** https://github.com/NopeCHALLC/nopecha-extension (10.3k★)
- **Website:** https://nopecha.com
- **Loại:** Browser extension + API giải captcha tự động bằng AI multimodal
- **License:** MIT (extension), closed-source AI backend (từ 2023)

## Supported Captcha Types

| Loại | Hỗ trợ |
|---|---|
| reCAPTCHA (v2/v3) | ✅ |
| hCaptcha (image, video, bounding-box, drag-and-drop) | ✅ |
| FunCAPTCHA | ✅ |
| Cloudflare Turnstile | ✅ |
| AWS WAF CAPTCHA | ✅ |
| Text-based CAPTCHA | ✅ |
| GeeTest | ✅ |

## Pricing

- **Free:** 100 requests/ngày, không cần API key, không cần signup
- **Paid plans:** Xem https://nopecha.com cho higher limits

## Cách tích hợp với Camoufox

NopeCHA có Firefox extension — có thể load trực tiếp qua `addons` parameter của Camoufox:

```python
async with AsyncCamoufox(
    headless=False,
    os="windows",
    addons=["/path/to/nopecha.xpi"],  # Firefox add-on file
) as browser:
    page = await browser.new_page()
    # Extension tự detect & solve captcha trên page
```

### Bước thực hiện (khi quyết định tích hợp):

1. Download NopeCHA Firefox add-on (.xpi) từ https://www.nopecha.com/firefox
2. Lưu vào `addons/nopecha.xpi` trong project
3. Pass vào `addons` parameter khi launch Camoufox
4. Extension tự động detect captcha trên page và giải
5. Test với các registrar có Turnstile/reCAPTCHA

### Lưu ý quan trọng:

- **Turnstile "undetectable mouse"** (v0.5.4+) chỉ Chromium-only. Firefox extension
  vẫn hoạt động nhưng dùng cơ chế click khác, có thể kém stealth hơn.
- **v0.5.5** (Jan 2026): cải thiện hCaptcha bounding-box, mouse action stability.
- Extension tự nhận diện captcha — **không cần code custom** per-captcha-type.
- AI backend dùng online RL pipeline, tự cập nhật khi captcha thay đổi.

## So sánh với hệ thống captcha hiện tại

| Aspect | Hiện tại (capsolver.py) | NopeCHA |
|---|---|---|
| Providers | 4 API (YesCaptcha → EZCaptcha → 2Captcha → CapSolver) + 2 local | 1 extension |
| Setup | Cần 4 API keys, config captcha.yaml | Install extension, optional API key |
| Cách hoạt động | Gửi screenshot/sitekey → nhận token → inject | Extension tự detect, solve trên page |
| Loại captcha | Chủ yếu Turnstile, reCAPTCHA | Tất cả loại phổ biến |
| Cost | Trả tiền per-solve, mỗi provider khác giá | Free 100/ngày, paid nếu cần nhiều |
| Maintenance | Phải maintain multi-provider fallback chain | Extension tự cập nhật |

## SDKs / API

- **Python:** `pip install nopecha`
- **Node.js:** `npm install nopecha`
- **API docs:** https://nopecha.com/api-reference/
- **Demo:** https://nopecha.com/captcha

## Khi nào nên tích hợp

- Khi captcha system hiện tại gặp vấn đề (rate limit, giải sai nhiều)
- Khi cần giải nhiều loại captcha mới (hCaptcha video, FunCAPTCHA)
- Khi muốn giảm complexity của captcha.yaml multi-provider setup
- Khi free tier 100 req/ngày đủ dùng (hoặc sẵn sàng trả plan)
