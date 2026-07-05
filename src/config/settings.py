"""
AppConfig - immutable configuration loaded from config.yaml.
Single Responsibility: owns config shape and loading logic only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, MISSING
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TimeoutConfig:
    email_wait: int = 120
    page_load: int = 20_000
    poll_interval: int = 4
    step_delay: int = 1_500
    click_delay: int = 500
    short_delay: int = 300
    nav_delay: int = 2_000
    sign_in_delay: int = 3_000
    batch_delay_sec: int = 5
    probe_timeout_ms: int = 3_000
    popup_close_probe_ms: int = 2_000


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "http://localhost:8317/v1"
    api_key: str = "ccs-internal-managed"
    model: str = "gpt-5.4"
    max_tokens: int = 2_560
    verify_max_tokens: int = 640


@dataclass(frozen=True)
class CaptchaConfig:
    max_rounds: int = 15
    checkbox_wait_sec: int = 12
    challenge_poll_ms: int = 1_000
    challenge_min_w: int = 300
    challenge_min_h: int = 250
    click_delay_ms: int = 400
    post_click_wait_ms: int = 600
    post_verify_wait_ms: int = 2_500
    recheck_wait_ms: int = 3_000
    pre_solve_wait_ms: int = 600
    drag_steps: int = 20
    drag_settle_ms: int = 400
    ezcaptcha_api_key: str = field(default_factory=lambda: os.getenv("EZCAPTCHA_API_KEY", ""))
    yescaptcha_api_key: str = field(default_factory=lambda: os.getenv("YESCAPTCHA_API_KEY", ""))
    twocaptcha_api_key: str = field(default_factory=lambda: os.getenv("TWOCAPTCHA_API_KEY", ""))
    capsolver_api_key: str = field(default_factory=lambda: os.getenv("CAPSOLVER_API_KEY", ""))
    # patchright: solve locally, không cần API key
    use_patchright: bool = False
    patchright_headless: bool = True
    # Turnstile-Solver local server (github.com/Theyka/Turnstile-Solver)
    # Để trống = không dùng, ví dụ: "http://127.0.0.1:5000"
    turnstile_solver_url: str = field(default_factory=lambda: os.getenv("TURNSTILE_SOLVER_URL", ""))
    # Timing / HTTP timeouts cho captcha API calls
    poll_interval_sec: int = 3
    max_wait_sec: int = 120
    create_task_timeout_sec: int = 30
    poll_result_timeout_sec: int = 10
    balance_timeout_sec: int = 15
    turnstile_solver_timeout_sec: int = 15
    # patchright browser settings
    patchright_viewport_width: int = 1280
    patchright_viewport_height: int = 800
    patchright_page_load_timeout_ms: int = 40_000
    patchright_poll_interval_sec: float = 0.5
    # Provider base URLs và task types
    yescaptcha_base: str = "https://api.yescaptcha.com"
    yescaptcha_turnstile_task: str = "TurnstileTaskProxyless"
    ezcaptcha_base: str = "https://api.ez-captcha.com"
    ezcaptcha_turnstile_task: str = "CloudFlareTurnstileTask"
    twocaptcha_base: str = "https://api.2captcha.com"
    twocaptcha_turnstile_task: str = "TurnstileTaskProxyless"
    capsolver_base: str = "https://api.capsolver.com"
    capsolver_turnstile_task: str = "AntiTurnstileTaskProxyless"


@dataclass(frozen=True)
class ElevenLabsConfig:
    signup_url: str = "https://elevenlabs.io/app/sign-up"
    api_keys_url: str = "https://elevenlabs.io/app/developers/api-keys"
    app_base_url: str = "elevenlabs.io/app"
    captcha_load_wait_ms: int = 4_000
    api_user_url: str = "https://api.elevenlabs.io/v1/user"
    check_timeout_sec: int = 10
    use_google_session: bool = True
    api_key_regex: str = r"sk_[a-f0-9]{20,}"


@dataclass(frozen=True)
class ChatGPTConfig:
    # OAuth2 PKCE constants (from CLIProxyAPI / openai-cli)
    oauth_authorize_url: str = "https://auth.openai.com/oauth/authorize"
    oauth_token_url: str = "https://auth.openai.com/oauth/token"
    client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"
    redirect_uri: str = "http://localhost:1455/auth/callback"
    callback_port: int = 1455
    otp_wait_sec: int = 90
    otp_poll_interval: int = 4
    post_submit_wait_ms: int = 3_000
    callback_timeout_sec: int = 300
    # Check API endpoints
    me_url: str = "https://api.openai.com/v1/me"
    quota_url: str = "https://chatgpt.com/backend-api/wham/usage"
    # User-agent strings dùng cho checker
    codex_ua: str = "codex_cli_rs/0.101.0 (Mac OS 26.0.1; arm64) Apple_Terminal/464"
    quota_ua: str = "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal"
    weekly_quota_window_sec: int = 604800
    # HTTP timeouts (giây)
    refresh_token_timeout_sec: int = 20
    check_me_timeout_sec: int = 10
    fetch_quota_timeout_sec: int = 10
    # Random birthyear range cho registration form
    birthyear_min: int = 1985
    birthyear_max: int = 1999
    birthyear_alt_min: int = 1975
    birthyear_alt_max: int = 1998
    # Batch concurrency
    batch_concurrency: int = 10
    confirm_rounds: int = 5
    token_expiry_buffer_sec: int = 300


@dataclass(frozen=True)
class LeonardoConfig:
    login_url: str = "https://app.leonardo.ai/auth/login"
    app_url_contains: str = "app.leonardo.ai"
    verification_sender: str = "leonardo.ai"
    otp_wait_sec: int = 180
    otp_poll_interval: int = 4
    post_submit_wait_ms: int = 3_000
    turnstile_timeout_sec: int = 300
    verification_code_regex: str = r"\b(\d{6,8})\b"


@dataclass(frozen=True)
class KlingAIConfig:
    login_url: str = "https://app.klingai.com/global/"
    app_url_contains: str = "klingai.com"
    session_dir: str = "data/kling_sessions"
    login_timeout_sec: int = 180
    post_login_wait_ms: int = 2_000
    refresh_start_url: str = "https://app.klingai.com/global/"
    refresh_target_url: str = "https://app.klingai.com/global/text-to-image/creation"
    refresh_start_timeout_ms: int = 60_000
    refresh_target_timeout_ms: int = 30_000
    refresh_start_wait_ms: int = 5_000
    refresh_target_wait_ms: int = 3_000


@dataclass(frozen=True)
class MailosaurConfig:
    signup_url: str = "https://mailosaur.com/app/signup"
    keys_url: str = "https://mailosaur.com/app/keys"
    keys_page_timeout_ms: int = 30_000
    click_timeout_ms: int = 10_000
    wait_url_timeout_ms: int = 25_000


@dataclass(frozen=True)
class TestmailConfig:
    signup_url: str = "https://testmail.app/signup/"
    console_url: str = "https://testmail.app/console/"
    otp_wait_sec: int = 90
    otp_poll_interval: int = 5
    max_retries: int = 3


@dataclass(frozen=True)
class CloudflareConfig:
    signup_url: str = "https://dash.cloudflare.com/sign-up"
    login_url: str = "https://dash.cloudflare.com/login"
    token_create_url_template: str = "https://dash.cloudflare.com/{account_id}/api-tokens/create"
    app_url_contains: str = "dash.cloudflare.com"
    verification_wait_sec: int = 180
    onboarding_skip_wait_ms: int = 2_000
    post_submit_wait_ms: int = 3_000
    check_timeout_sec: int = 15
    # Selectors for signup/onboarding/token UI
    email_selector: str = 'input[name="email"]'
    password_selector: str = 'input[type="password"]'
    signup_button_text: str = 'Sign up'
    skip_button_texts: tuple[str, ...] = ('Skip', 'Skip for now', 'Not now')
    ai_section_name: str = 'AI & machine learning'
    ai_gateway_run_label: str = 'AI Gateway'
    ai_search_run_label: str = 'AI Search'
    workers_ai_read_label: str = 'Workers AI'
    review_button_text: str = 'Review token'
    create_button_text: str = 'Create Token'
    token_display_label: str = 'Your API Token'
    token_regex: str = r'[A-Za-z0-9_-]{40,}'
    account_id_regex: str = r'dash\.cloudflare\.com/([0-9a-f]{32})/'


@dataclass(frozen=True)
class NineRouterConfig:
    """9Router dashboard — service riêng, tao chỉ dùng (không quản lý code).

    Dùng để auto-add Cloudflare account sau khi tạo: fill form Add → Check → Save.
    Selectors/timeouts cho task add_cf_to_9router — DOM đã verify 2026-07-04.
    password đọc qua env NINEROUTER_PASSWORD.
    """
    dashboard_url: str = "http://localhost:20128/dashboard/providers/cloudflare-ai"
    password: str = field(default_factory=lambda: os.getenv("NINEROUTER_PASSWORD", ""))
    login_path: str = "/login"
    target_path: str = "/cloudflare-ai"
    login_password_selector: str = 'input[placeholder="Enter password"]'
    login_button_text: str = "Login"
    login_password_visible_timeout_ms: int = 10_000
    login_redirect_timeout_ms: int = 15_000
    add_button_xpath: str = 'xpath=//button[normalize-space()="addAdd"]'
    add_panel_h2: str = "Add Cloudflare API Key"
    add_button_visible_timeout_ms: int = 10_000
    add_panel_visible_timeout_ms: int = 10_000
    name_input_selector: str = 'input[placeholder="Production Key"]'
    api_key_input_selector: str = 'input[type="password"]'
    account_id_input_selector: str = 'input[placeholder="abc123def456..."]'
    check_button_text: str = "Check"
    check_enable_timeout_ms: int = 10_000
    badge_valid_text: str = "Valid"
    badge_invalid_text: str = "Invalid"
    badge_visible_timeout_ms: int = 30_000
    save_button_text: str = "Save"
    save_enable_timeout_ms: int = 5_000
    save_panel_hidden_timeout_ms: int = 15_000
    button_enable_poll_interval_ms: int = 150


@dataclass(frozen=True)
class GmailLoginConfig:
    """Gmail TOTP 2FA login flow (src/services/gmail/login.py).
    Khác google_oauth (OAuth chooser) — đây là direct login với TOTP."""
    signin_url: str = "https://accounts.google.com/signin"
    success_url: str = "myaccount.google.com"
    email_input: str = 'input[type="email"]'
    email_next: str = "#identifierNext"
    password_input: str = 'input[name="Passwd"]'
    password_next: str = "#passwordNext"
    challenge_totp: str = '[data-challengetype="6"]'
    totp_input: str = 'input[name="totpPin"]'
    totp_next: str = '[id$="Next"]'
    post_email_delay_sec: float = 1.5
    post_password_delay_sec: float = 2.0
    post_challenge_click_delay_sec: float = 2.0
    post_totp_delay_sec: float = 3.0
    challenge_visible_timeout_ms: int = 10_000
    totp_visible_timeout_ms: int = 10_000


@dataclass(frozen=True)
class ProtonConfig:
    """Proton Mail registration — selectors/texts/timeouts cho register_proton."""
    signup_url: str = "https://account.proton.me/signup?plan=free"
    signup_page_load_multiplier: int = 3
    signup_iframe_selector: str = "iframe"
    signup_iframe_url_contains: str = "Name=email"
    username_selector: str = "#username"
    username_taken_text: str = "Username already used"
    username_max_attempts: int = 5
    signup_iframe_timeout_ms: int = 30_000
    password_selector: str = "#password"
    password_confirm_selector: str = "#password-confirm"
    submit_selector: str = 'button[type="submit"]'
    create_account_button_text: str = "Create account"
    dismiss_popup_texts: tuple[str, ...] = ("Skip", "Maybe later", "No, thanks", "Not now")


@dataclass(frozen=True)
class MailConfig:
    cooldown_sec: int = 120
    max_consecutive_fails: int = 3
    db_path: Path = field(default_factory=lambda: Path("data/accounts.db"))
    retryable_status_codes: tuple[int, ...] = field(default_factory=lambda: (429, 500, 502, 503, 504))
    http_timeout_sec: int = 15
    wait_timeout_sec: int = 120
    poll_interval_sec: int = 5
    max_retries: int = 3
    retry_max_delay_sec: int = 30
    mail_tm_bases: tuple[str, ...] = field(default_factory=lambda: ("https://api.mail.tm",))
    testmail_base_url: str = "https://api.testmail.app"
    mailosaur_base_url: str = "https://mailosaur.com/api"
    guerrillamail_base_url: str = "https://www.guerrillamail.com/ajax.php"
    gmail_base_url: str = "https://mail.google.com"
    gmail_inbox_url: str = "https://mail.google.com/mail/u/0/#inbox"
    gmail_search_url_template: str = "https://mail.google.com/mail/u/0/#search/{query}"
    sms_store_cap: int = 500

    def providers_for(self, service: str = '') -> tuple[str, ...]:
        import asyncio
        import os
        import concurrent.futures
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import get_mail_providers_async
        tag = service.strip().lower() or None
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return ()
        
        async def _fetch():
            init_async_db(db_url)
            async with get_async_session() as session:
                return await get_mail_providers_async(session, service_tag=tag)
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # Running in async context - run in separate thread
            with concurrent.futures.ThreadPoolExecutor() as pool:
                rows = pool.submit(asyncio.run, _fetch()).result()
        else:
            rows = asyncio.run(_fetch())
        
        return tuple(str(r['connection_str']) for r in rows if r.get('connection_str'))


@dataclass(frozen=True)
class GoogleOAuthConfig:
    login_url: str = "https://accounts.google.com/signin/v2/identifier"
    myaccount_url: str = "https://myaccount.google.com"
    login_timeout_ms: int = 60_000
    popup_close_timeout_ms: int = 30_000
    password_visible_timeout_ms: int = 15_000
    password_next_timeout_ms: int = 10_000
    account_chooser_timeout_ms: int = 5_000
    account_chooser_click_timeout_ms: int = 15_000
    consent_timeout_ms: int = 8_000
    phone_input_timeout_ms: int = 10_000
    phone_send_timeout_ms: int = 5_000
    otp_input_timeout_ms: int = 10_000
    otp_next_timeout_ms: int = 5_000
    totp_candidate_timeout_ms: int = 8_000
    totp_next_timeout_ms: int = 5_000
    page_load_timeout_ms: int = 10_000
    authenticator_probe_timeout_ms: int = 3_000
    phone_probe_timeout_ms: int = 3_000
    try_another_way_timeout_ms: int = 8_000
    popup_close_event_timeout_ms: int = 15_000
    auth_handler_redirect_timeout_ms: int = 15_000
    sms_otp_timeout_sec: int = 300
    sms_otp_poll_interval_sec: int = 3
    popup_max_iterations: int = 30
    login_max_iterations: int = 20
    popup_deadline_multiplier: int = 3

@dataclass(frozen=True)
class LogConsoleConfig:
    enabled: bool = True
    level: str = "INFO"
    format: str = "%(message)s"


@dataclass(frozen=True)
class LogFileConfig:
    enabled: bool = True
    level: str = "DEBUG"
    path: str = "logs/app.log"
    format: str = "[%(asctime)s] [%(levelname)-5s] %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5


@dataclass(frozen=True)
class AllLogConfig:
    """Config cho all.log — tee stdout+stderr ra file."""
    enabled: bool = True
    path: str = "logs/all.log"
    append: bool = False


@dataclass(frozen=True)
class LogConfig:
    append: bool = False
    level: str = "DEBUG"
    console: LogConsoleConfig = field(default_factory=LogConsoleConfig)
    file: LogFileConfig = field(default_factory=LogFileConfig)
    all_log: AllLogConfig = field(default_factory=AllLogConfig)


@dataclass(frozen=True)
class AuthSyncConfig:
    enabled: bool = True
    target_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("AUTH_SYNC_TARGET_DIR",
                      str(Path.home() / ".ccs" / "cliproxy" / "auth"))
        )
    )


@dataclass(frozen=True)
class ClipRoxySyncConfig:
    """Config cho việc sync OpenRouter API keys qua CLIProxyAPI Management REST API."""
    management_url: str = field(
        default_factory=lambda: os.getenv("CLIPROXY_MANAGEMENT_URL", "http://localhost:8317")
    )
    management_key: str = field(
        default_factory=lambda: os.getenv("CLIPROXY_MANAGEMENT_KEY", "ccs")
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "https://ollama.com/v1"
    http_timeout_sec: int = 10
    # 9router db.json path - tùy chỉnh cho sync Ollama
    ninerouter_db_path: Path | None = None


@dataclass(frozen=True)
class RegisterConfig:
    max_attempts: int = 3
    password_length: int = 14


@dataclass(frozen=True)
class RegistrationConfig:
    """Giới hạn vận hành cho registration API (jobs, workers) và JobStore."""
    max_jobs: int = 500
    max_consecutive_fails: int = 10
    max_count: int = 1000
    max_workers: int = 10


@dataclass(frozen=True)
class ApiConfig:
    """Config cho FastAPI server (CORS, etc.)."""
    cors_origins: tuple[str, ...] = field(default_factory=lambda: (
        "http://localhost:1420",
        "http://localhost:1421",
        "tauri://localhost",
    ))
    # URL cua host-browser-agent (chay tren host OS).
    host_browser_agent_url: str = field(default_factory=lambda: os.getenv("HOST_BROWSER_AGENT_URL", ""))
    # Internal API key (X-Internal-Key header, service-to-service). Local 1-user:
    # default ccs-internal, override qua env INTERNAL_API_KEY khi cần.
    internal_api_key: str = field(default_factory=lambda: os.getenv("INTERNAL_API_KEY", "ccs-internal"))
    # Browser Gateway (host_browser_agent.py) bind host/port.
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 9999
    gateway_ws_poll_interval_ms: int = 500


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool = True
    server: str = ""        # http://host:port
    username: str = ""
    password: str = ""


@dataclass(frozen=True)
class ArtificialAnalysisConfig:
    login_url: str = "https://artificialanalysis.ai/login"
    app_url_contains: str = "artificialanalysis.ai"
    magic_link_wait_sec: int = 120
    post_submit_wait_ms: int = 3_000
    base_url: str = "https://artificialanalysis.ai"
    image_lab_url: str = "https://artificialanalysis.ai/image/image-lab"
    terms_acceptance_url: str = "https://artificialanalysis.ai/api/playground/terms-acceptance"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    check_timeout_sec: int = 15
    # aa_proxy.py HTTP timeouts (giây) + concurrency semaphores
    post_timeout_sec: int = 60
    generate_timeout_sec: int = 120
    image_proxy_timeout_sec: int = 30
    r2_download_timeout_sec: int = 60
    check_sessions_concurrency: int = 15
    accept_terms_concurrency: int = 20
    api_key_regex: str = r"aa_[a-zA-Z0-9_-]{10,}"
    # Image Lab macro timing
    image_lab_login_wait_ms: int = 3_000
    image_lab_poll_interval_ms: int = 3_000
    image_lab_generation_timeout_sec: int = 300
    # Browser Gateway (host native camoufox) — container reach qua host.docker.internal.
    # Env-driven: không declare trong YAML (empty string override env).
    host_browser_agent_url: str = field(default_factory=lambda: os.getenv("HOST_BROWSER_AGENT_URL", ""))


@dataclass(frozen=True)
class GmailVariationsConfig:
    """Cấu hình cho Gmail alias variation generator."""
    # Dot trick: username dài hơn ngưỡng này → chỉ sample 3 biến thể thay vì enumerate toàn bộ 2^(n-1)
    dot_max_username_len: int = 12
    # Mẫu fallback khi username vượt dot_max_username_len: [full, mid, full_dots]
    dot_long_sample_mid_divisor: int = 2
    # Plus tags mặc định khi user không cung cấp
    default_plus_tags: tuple[str, ...] = field(default_factory=lambda: tuple(str(i) for i in range(1, 21)))
    # Giá trị mặc định cho UI — techniques nào được check sẵn
    ui_default_use_plus: bool = True
    ui_default_use_dot: bool = False
    ui_default_use_googlemail: bool = False
    # Plus tags hiển thị sẵn trong UI input
    ui_default_plus_tags: str = "1,2,3,4,5,6,7,8,9,10"


@dataclass(frozen=True)
class SentryConfig:
    dsn: str = field(default_factory=lambda: os.getenv("SENTRY_DSN", ""))
    environment: str = field(default_factory=lambda: os.getenv("SENTRY_ENV", "production"))
    traces_sample_rate: float = 0.1
    profiles_sample_rate: float = 0.0
    send_default_pii: bool = False


@dataclass(frozen=True)
class OpenRouterConfig:
    signup_url: str = "https://openrouter.ai/sign-up"
    app_url_contains: str = "openrouter.ai"
    turnstile_sitekey: str = "0x4AAAAAAAWXJGBD7bONzLBd"
    otp_wait_sec: int = 90
    otp_poll_interval: int = 4
    post_submit_wait_ms: int = 3_000
    # Checker
    key_check_url: str = "https://openrouter.ai/api/v1/key"
    chat_completions_url: str = "https://openrouter.ai/api/v1/chat/completions"
    privacy_check_model: str = "minimax/minimax-m2.5:free"
    check_timeout_sec: int = 15
    # Check-and-clean
    base_api_url: str = "https://openrouter.ai/api/v1"
    sign_in_url: str = "https://openrouter.ai/sign-in"
    privacy_settings_url: str = "https://openrouter.ai/settings/privacy"
    keys_settings_url: str = "https://openrouter.ai/settings/keys"
    check_clean_model: str = "minimax/minimax-m2.5:free"
    check_clean_max_tokens: int = 5
    check_clean_timeout_sec: int = 20
    login_poll_interval_ms: int = 1_000
    privacy_toggle_wait_ms: int = 600
    api_key_regex: str = r"sk-or-[a-zA-Z0-9_\-]{20,}"


@dataclass(frozen=True)
class CheckerConfig:
    batch_concurrency: int = 10
    check_and_clean_concurrency: int = 20
    fix_privacy_concurrency: int = 3


@dataclass(frozen=True)
class DatabaseConfig:
    busy_timeout_ms: int = 5000
    retry_max_retries: int = 3
    retry_base_delay_sec: float = 0.1
    # Environment: dev|prod|test. Defaults to APP_ENV or "prod".
    env: str = ""
    # PostgreSQL connection URL. If set, uses async PostgreSQL instead of SQLite.
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))


@dataclass(frozen=True)
class AppConfig:
    log: LogConfig = field(default_factory=LogConfig)
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 720
    # Số camoufox task tối đa chạy đồng thời trên Browser Gateway host.
    # Phải >= registration.max_workers, nếu không worker thừa sẽ chờ (worker ≠ luồng).
    max_concurrent: int = 10
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    captcha: CaptchaConfig = field(default_factory=CaptchaConfig)
    register: RegisterConfig = field(default_factory=RegisterConfig)
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    elevenlabs: ElevenLabsConfig = field(default_factory=ElevenLabsConfig)
    chatgpt: ChatGPTConfig = field(default_factory=ChatGPTConfig)
    openrouter: OpenRouterConfig = field(default_factory=OpenRouterConfig)
    artificialanalysis: ArtificialAnalysisConfig = field(default_factory=ArtificialAnalysisConfig)
    gmail_variations: GmailVariationsConfig = field(default_factory=GmailVariationsConfig)
    leonardo: LeonardoConfig = field(default_factory=LeonardoConfig)
    klingai: KlingAIConfig = field(default_factory=KlingAIConfig)
    mailosaur: MailosaurConfig = field(default_factory=MailosaurConfig)
    testmail: TestmailConfig = field(default_factory=TestmailConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    google_oauth: GoogleOAuthConfig = field(default_factory=GoogleOAuthConfig)
    auth_sync: AuthSyncConfig = field(default_factory=AuthSyncConfig)
    cliproxy_sync: ClipRoxySyncConfig = field(default_factory=ClipRoxySyncConfig)
    sentry: SentryConfig = field(default_factory=SentryConfig)
    checker: CheckerConfig = field(default_factory=CheckerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)
    ninerouter: NineRouterConfig = field(default_factory=NineRouterConfig)
    proton: ProtonConfig = field(default_factory=ProtonConfig)
    gmail_login: GmailLoginConfig = field(default_factory=GmailLoginConfig)
    proxy: ProxyConfig | None = None
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    @property
    def screenshot_dir(self) -> Path:
        return self.base_dir / "screenshots"

    @property
    def debug_dir(self) -> Path:
        return self.base_dir / "debug"

    @property
    def log_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def log_file(self) -> Path:
        return self.base_dir / self.log.file.path

    def init_async_db(self) -> None:
        """Initialize async PostgreSQL connection if database_url is set."""
        if self.database.database_url:
            from common.database._engine import init_async_db
            init_async_db(self.database.database_url)


def _strict(section: dict, key: str, section_name: str):
    """Lấy giá trị từ dict — thiếu key thì raise ngay, không fallback."""
    if key not in section:
        raise KeyError(
            f"Missing required config key '{key}' in section '{section_name}'"
        )
    return section[key]


def _require_section(raw: dict, name: str) -> dict:
    """Get a top-level section from merged config. Return empty dict if missing."""
    return raw.get(name) or {}


def _parse_section_strict(cls, raw: dict, section_name: str):
    """Parse a config section — validate required fields, use defaults for optional.

    Fields with defaults are optional (use default if missing).
    Fields without defaults are required.
    """
    kwargs = {}
    for key, fld in cls.__dataclass_fields__.items():
        if key not in raw:
            if fld.default is not MISSING or fld.default_factory is not MISSING:
                # Has default → optional, skip
                continue
            raise KeyError(
                f"Missing required config key '{key}' in section '{section_name}'"
            )
        val = raw[key]
        type_str = str(fld.type)
        if "tuple" in type_str and isinstance(val, list):
            val = tuple(val)
        elif "Path" in type_str and isinstance(val, str):
            val = Path(val)
        kwargs[key] = val
    return cls(**kwargs)


def _parse_log(raw: dict) -> LogConfig:
    if not raw:
        raise KeyError("Missing 'log' section in config. Check config/logging.yaml")

    console_raw = raw.get("console") or {}
    file_raw = raw.get("file") or {}
    all_log_raw = raw.get("all_log") or {}

    console = _parse_section_strict(LogConsoleConfig, console_raw, "log.console")
    file_cfg = _parse_section_strict(LogFileConfig, file_raw, "log.file")
    all_log = _parse_section_strict(AllLogConfig, all_log_raw, "log.all_log")

    # Build LogConfig with parsed nested objects
    return LogConfig(
        append=raw.get("append", False),
        level=raw.get("level", "DEBUG"),
        console=console,
        file=file_cfg,
        all_log=all_log,
    )


def _parse_auth_sync(raw: dict) -> AuthSyncConfig:
    return _parse_section_strict(AuthSyncConfig, raw, "auth_sync")


def _parse_proxy(raw: dict) -> ProxyConfig | None:
    """Parse proxy section. Trả None nếu section rỗng/thiếu. Nếu có thì strict."""
    if not raw:
        return None
    return _parse_section_strict(ProxyConfig, raw, "proxy")


def _parse_cliproxy_sync(raw: dict) -> ClipRoxySyncConfig:
    return _parse_section_strict(ClipRoxySyncConfig, raw, "cliproxy_sync")


def seed_mail_providers(cfg: AppConfig) -> None:
    """Mail providers are seeded through PostgreSQL migration/import paths."""
    return None


def _parse_mail(raw: dict, db_path: Path) -> MailConfig:
    """Parse MailConfig from YAML dict.
    db_path is injected programmatically — not from YAML.
    Note: auto-seeding providers is done in seed_mail_providers(), not here."""
    return MailConfig(
        cooldown_sec=int(raw.get("cooldown_sec", 120)),
        max_consecutive_fails=int(raw.get("max_consecutive_fails", 3)),
        db_path=db_path,
        retryable_status_codes=tuple(int(c) for c in raw.get("retryable_status_codes", (429, 500, 502, 503, 504))),
        http_timeout_sec=int(raw.get("http_timeout_sec", 15)),
        wait_timeout_sec=int(raw.get("wait_timeout_sec", 120)),
        poll_interval_sec=int(raw.get("poll_interval_sec", 5)),
        max_retries=int(raw.get("max_retries", 3)),
        retry_max_delay_sec=int(raw.get("retry_max_delay_sec", 30)),
        mail_tm_bases=tuple(str(b) for b in raw.get("mail_tm_bases", ("https://api.mail.tm",))),
        testmail_base_url=str(raw.get("testmail_base_url", "https://api.testmail.app")),
        mailosaur_base_url=str(raw.get("mailosaur_base_url", "https://mailosaur.com/api")),
        guerrillamail_base_url=str(raw.get("guerrillamail_base_url", "https://www.guerrillamail.com/ajax.php")),
        gmail_base_url=str(raw.get("gmail_base_url", "https://mail.google.com")),
        gmail_inbox_url=str(raw.get("gmail_inbox_url", "https://mail.google.com/mail/u/0/#inbox")),
        gmail_search_url_template=str(raw.get("gmail_search_url_template", "https://mail.google.com/mail/u/0/#search/{query}")),
        sms_store_cap=int(raw.get("sms_store_cap", 500)),
    )


def _parse_gmail_variations(raw: dict) -> GmailVariationsConfig:
    return _parse_section_strict(GmailVariationsConfig, raw, "gmail_variations")


_CONFIG_DIR_NAME = "config"
_CONFIG_FILES = (
    "config.yaml",
    "platform.yaml",
    "logging.yaml",
    "mail.yaml",
    "captcha.yaml",
    # Per-service configs
    "elevenlabs.yaml",
    "openrouter.yaml",
    "chatgpt.yaml",
    "leonardo.yaml",
    "klingai.yaml",
    "mailosaur.yaml",
    "testmail.yaml",
    "artificialanalysis.yaml",
    "sentry.yaml",
    "cloudflare.yaml",
    "ninerouter.yaml",
    "proton.yaml",
    "gmail.yaml",
)


def _load_raw(base_dir: Path) -> dict:
    """Merge tất cả config files từ config/ folder — file sau override file trước."""
    cfg_dir = base_dir / _CONFIG_DIR_NAME
    raw: dict = {}
    for name in _CONFIG_FILES:
        p = cfg_dir / name
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            raw.update(data)
    return raw


def _parse_registration(raw: dict) -> RegistrationConfig:
    return _parse_section_strict(RegistrationConfig, raw, "registration")


def _parse_api(raw: dict) -> ApiConfig:
    return _parse_section_strict(ApiConfig, raw, "api")


def _parse_checker(raw: dict | None) -> CheckerConfig:
    if not raw:
        return CheckerConfig()
    return _parse_section_strict(CheckerConfig, raw, "checker")


def _parse_mailosaur(raw: dict | None) -> MailosaurConfig:
    if not raw:
        return MailosaurConfig()
    return _parse_section_strict(MailosaurConfig, raw, "mailosaur")


def _parse_cloudflare(raw: dict | None) -> CloudflareConfig:
    if not raw:
        return CloudflareConfig()
    return _parse_section_strict(CloudflareConfig, raw, "cloudflare")


def _parse_ninerouter(raw: dict | None) -> NineRouterConfig:
    if not raw:
        return NineRouterConfig()
    return _parse_section_strict(NineRouterConfig, raw, "ninerouter")


def _parse_proton(raw: dict | None) -> ProtonConfig:
    if not raw:
        return ProtonConfig()
    return _parse_section_strict(ProtonConfig, raw, "proton")


def _parse_gmail_login(raw: dict | None) -> GmailLoginConfig:
    if not raw:
        return GmailLoginConfig()
    return _parse_section_strict(GmailLoginConfig, raw, "gmail")


def _parse_database(raw: dict | None) -> DatabaseConfig:
    if not raw:
        return DatabaseConfig()
    return _parse_section_strict(DatabaseConfig, raw, "database")


def load_config(path: Path | None = None) -> AppConfig:
    """Load config từ config/*.yaml -> AppConfig. Ném lỗi nếu config không load được."""
    if path is None:
        base_dir = Path(__file__).parent.parent.parent
    else:
        # path có thể là file hoặc folder: nếu là file thì lấy parent của parent (project root)
        base_dir = path.parent if path.is_dir() else path.parent.parent if path.parent.name == _CONFIG_DIR_NAME else path.parent
    raw = _load_raw(base_dir)

    # Resolve APP_ENV and DB path
    from common.env import APP_ENV, db_path as _resolve_db_path
    _cfg_env = _parse_database(raw.get("database")).env
    _target_env = _cfg_env or APP_ENV
    db_path = _resolve_db_path(_target_env)

    browser_raw = _require_section(raw, "browser")
    return AppConfig(
        log=_parse_log(_require_section(raw, "log")),
        headless=_strict(browser_raw, "headless", "browser"),
        viewport_width=_strict(browser_raw, "viewport_width", "browser"),
        viewport_height=_strict(browser_raw, "viewport_height", "browser"),
        max_concurrent=_strict(browser_raw, "max_concurrent", "browser"),
        timeouts=_parse_section_strict(TimeoutConfig, _require_section(raw, "timeouts"), "timeouts"),
        llm=_parse_section_strict(LLMConfig, _require_section(raw, "llm"), "llm"),
        captcha=_parse_section_strict(CaptchaConfig, _require_section(raw, "captcha"), "captcha"),
        register=_parse_section_strict(RegisterConfig, _require_section(raw, "register"), "register"),
        registration=_parse_registration(_require_section(raw, "registration")),
        api=_parse_api(_require_section(raw, "api")),
        elevenlabs=_parse_section_strict(ElevenLabsConfig, _require_section(raw, "elevenlabs"), "elevenlabs"),
        chatgpt=_parse_section_strict(ChatGPTConfig, _require_section(raw, "chatgpt"), "chatgpt"),
        openrouter=_parse_section_strict(OpenRouterConfig, _require_section(raw, "openrouter"), "openrouter"),
        artificialanalysis=_parse_section_strict(ArtificialAnalysisConfig, _require_section(raw, "artificialanalysis"), "artificialanalysis"),
        gmail_variations=_parse_gmail_variations(_require_section(raw, "gmail_variations")),
        leonardo=_parse_section_strict(LeonardoConfig, _require_section(raw, "leonardo"), "leonardo"),
        klingai=_parse_section_strict(KlingAIConfig, _require_section(raw, "klingai"), "klingai"),
        mailosaur=_parse_mailosaur(raw.get("mailosaur")),
        testmail=_parse_section_strict(TestmailConfig, _require_section(raw, "testmail"), "testmail"),
        mail=_parse_mail(_require_section(raw, "mail"), db_path),
        google_oauth=_parse_section_strict(GoogleOAuthConfig, _require_section(raw, "google_oauth"), "google_oauth"),
        auth_sync=_parse_auth_sync(_require_section(raw, "auth_sync")),
        cliproxy_sync=_parse_cliproxy_sync(_require_section(raw, "cliproxy_sync")),
        sentry=_parse_section_strict(SentryConfig, _require_section(raw, "sentry"), "sentry"),
        checker=_parse_checker(raw.get("checker")),
        database=_parse_database(raw.get("database")),
        cloudflare=_parse_cloudflare(raw.get("cloudflare")),
        ninerouter=_parse_ninerouter(raw.get("ninerouter")),
        proton=_parse_proton(raw.get("proton")),
        gmail_login=_parse_gmail_login(raw.get("gmail")),
        proxy=_parse_proxy(raw.get("proxy", {})),
        base_dir=base_dir,
    )
