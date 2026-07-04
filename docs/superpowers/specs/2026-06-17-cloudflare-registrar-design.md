# Cloudflare Auto-Signup Registrar - Design Spec

## Goal
Thêm service CLOUDFLARE vào egistrar để tự động:
1. Tạo email qua 	estmail.app provider.
2. Signup tại https://dash.cloudflare.com/sign-up.
3. Tick Turnstile "Verify you are human".
4. Submit form và bỏ qua redirect-onboard giả mạo.
5. Đợi + mở link verify email từ Cloudflare.
6. Skip onboarding wizard.
7. Tạo API token với quyền AI Gateway Read, AI Search Run, Workers AI Run.
8. Lưu pi_key và ccount_id vào DB.

## Context
- CloudflareConfig đã tồn tại trong src/config/settings.py.
- Package src/services/cloudflare_com/ chỉ có __init__.py trống.
- Registry src/services/registry.py chưa đăng ký factory cho CLOUDFLARE.

## Approach
- Viết module FP src/services/cloudflare_com/registrar.py với egister_cloudflare(cfg, log_fn, save_fn).
- Sử dụng create_mailbox(cfg.mail.providers_for("cloudflare")) để lấy testmail.app mailbox.
- Mở signup page bằng open_browser(cfg).
- Fill email + password qua DOM selectors lấy thực tế; dump HTML sau mỗi action qua dump_debug_html.
- Giải Turnstile bằng cách click vào frame challenges.cloudflare.com (reuse OpenRouter).
- Submit signup; bỏ qua redirect onboard fake.
- Poll email verify từ testmail.app; extract link; navigate.
- Skip onboarding qua DOM selectors thực tế.
- Extract ccount_id từ URL dash.cloudflare.com/{account_id}/api-tokens/create.
- Navigate token create, tick AI Gateway Read, AI Search Run, Workers AI Run.
- Review -> Create token, extract token text.
- Trả AccountRecord(service="CLOUDFLARE", email, password, api_key, account_id).

## Error Handling
- NoMailboxAvailableError, CaptchaError, EmailVerificationError, RetryableRegistrationError.
- Không fallback, không nuốt lỗi business logic.

## Data Saved
- service="CLOUDFLARE", email, password, api_key (token), account_id.

## Testing
- Unit test resolve make_registrar("CLOUDFLARE").
- Smoke test load CloudflareConfig.