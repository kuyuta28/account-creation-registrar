"""
AppConfig - immutable configuration loaded from config.yaml.
Single Responsibility: owns config shape and loading logic only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class LeonardoConfig:
    login_url: str = "https://app.leonardo.ai/auth/login"
    app_url_contains: str = "app.leonardo.ai"
    verification_sender: str = "leonardo.ai"
    otp_wait_sec: int = 180
    otp_poll_interval: int = 4
    post_submit_wait_ms: int = 3_000
    turnstile_timeout_sec: int = 300


@dataclass(frozen=True)
class KlingAIConfig:
    login_url: str = "https://app.klingai.com/global/"
    app_url_contains: str = "klingai.com"
    session_dir: str = "data/kling_sessions"
    login_timeout_sec: int = 180
    post_login_wait_ms: int = 2_000


@dataclass(frozen=True)
class TwoSlidesConfig:
    login_url: str = "https://2slides.com/login"
    api_url: str = "https://2slides.com/api"
    app_url_contains: str = "2slides.com"
    otp_wait_sec: int = 120
    otp_poll_interval: int = 4
    post_submit_wait_ms: int = 3_000


@dataclass(frozen=True)
class TestmailConfig:
    otp_wait_sec: int = 90
    otp_poll_interval: int = 5
    max_retries: int = 3


@dataclass(frozen=True)
class MailConfig:
    cooldown_sec: int = 120
    max_consecutive_fails: int = 3
    db_path: Path = field(default_factory=lambda: Path("data/accounts.db"))
    retryable_status_codes: tuple[int, ...] = field(default_factory=lambda: (429, 500, 502, 503, 504))

    @property
    def all_providers(self) -> tuple[str, ...]:
        return self.providers_for()

    def providers_for(self, service: str = "") -> tuple[str, ...]:
        """Query DB cho active mail providers. service='' → tất cả. Trả tuple rỗng nếu không có."""
        from common.database import get_mail_providers
        rows = get_mail_providers(
            self.db_path,
            service_tag=service.lower() if service else None,
        )
        return tuple(r["connection_str"] for r in rows)


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


@dataclass(frozen=True)
class AppConfig:
    log: LogConfig = field(default_factory=LogConfig)
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 720
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
    twoslides: TwoSlidesConfig = field(default_factory=TwoSlidesConfig)
    testmail: TestmailConfig = field(default_factory=TestmailConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    auth_sync: AuthSyncConfig = field(default_factory=AuthSyncConfig)
    cliproxy_sync: ClipRoxySyncConfig = field(default_factory=ClipRoxySyncConfig)
    sentry: SentryConfig = field(default_factory=SentryConfig)
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


def _strict(section: dict, key: str, section_name: str):
    """Lấy giá trị từ dict — thiếu key thì raise ngay, không fallback."""
    if key not in section:
        raise KeyError(
            f"Missing required config key '{key}' in section '{section_name}'"
        )
    return section[key]


def _require_section(raw: dict, name: str) -> dict:
    """Require a top-level section in merged config. Raise nếu thiếu."""
    section = raw.get(name)
    if section is None:
        raise KeyError(f"Missing required section '{name}' in config YAML files")
    return section


def _parse_section_strict(cls, raw: dict, section_name: str):
    """Parse a config section — BẮT BUỘC tất cả fields trong dataclass phải có trong YAML.
    Tự động convert list→tuple và str→Path nếu cần."""
    kwargs = {}
    for key, fld in cls.__dataclass_fields__.items():
        if key not in raw:
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

    console_raw = raw.get("console")
    if console_raw is None:
        raise KeyError("Missing 'log.console' section in config/logging.yaml")
    file_raw = raw.get("file")
    if file_raw is None:
        raise KeyError("Missing 'log.file' section in config/logging.yaml")
    all_log_raw = raw.get("all_log")
    if all_log_raw is None:
        raise KeyError("Missing 'log.all_log' section in config/logging.yaml")

    console = LogConsoleConfig(
        enabled=bool(_strict(console_raw, "enabled", "log.console")),
        level=str(_strict(console_raw, "level", "log.console")),
        format=str(_strict(console_raw, "format", "log.console")),
    )
    file_cfg = LogFileConfig(
        enabled=bool(_strict(file_raw, "enabled", "log.file")),
        level=str(_strict(file_raw, "level", "log.file")),
        path=str(_strict(file_raw, "path", "log.file")),
        format=str(_strict(file_raw, "format", "log.file")),
        date_format=str(_strict(file_raw, "date_format", "log.file")),
        max_bytes=int(_strict(file_raw, "max_bytes", "log.file")),
        backup_count=int(_strict(file_raw, "backup_count", "log.file")),
    )
    all_log = AllLogConfig(
        enabled=bool(_strict(all_log_raw, "enabled", "log.all_log")),
        path=str(_strict(all_log_raw, "path", "log.all_log")),
        append=bool(_strict(all_log_raw, "append", "log.all_log")),
    )
    return LogConfig(
        append=bool(_strict(raw, "append", "log")),
        level=str(_strict(raw, "level", "log")),
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


def _auto_seed_mailslurp_keys(db_path: Path, keys: list[str]) -> None:
    """Seed mailslurp keys từ yaml vào mail_providers table (idempotent)."""
    from common.database import upsert_mail_provider, get_mail_providers
    existing = {r["connection_str"] for r in get_mail_providers(db_path)}
    for key in keys:
        if f"mailslurp.com:{key}" not in existing:
            label = f"mailslurp.com:...{key[-8:]}"
            upsert_mail_provider(db_path, "mailslurp.com", api_key=key, label=label)


def _auto_seed_free_providers(db_path: Path) -> None:
    """Seed FREE providers (no API key needed): mail.tm, guerrillamail.com."""
    from common.database import upsert_mail_provider, get_mail_providers
    existing = {r["connection_str"] for r in get_mail_providers(db_path)}
    # mail.tm — server_id chứa base URL
    if "https://api.mail.tm" not in existing:
        upsert_mail_provider(db_path, "mail.tm", api_key="", server_id="https://api.mail.tm", label="mail.tm")
    # Guerrilla Mail — không cần key
    if "guerrillamail.com" not in existing:
        upsert_mail_provider(db_path, "guerrillamail.com", api_key="", server_id="", label="Guerrilla Mail")


def _parse_mail(raw: dict, db_path: Path) -> MailConfig:
    """Parse MailConfig. Auto-seed providers: mailslurp (from yaml), free providers.
    db_path is injected programmatically — not from YAML."""
    mailslurp_keys = [str(k).strip() for k in raw.get("mailslurp_api_keys", []) if str(k).strip()]
    if mailslurp_keys:
        _auto_seed_mailslurp_keys(db_path, mailslurp_keys)
    _auto_seed_free_providers(db_path)
    return MailConfig(
        cooldown_sec=int(_strict(raw, "cooldown_sec", "mail")),
        max_consecutive_fails=int(_strict(raw, "max_consecutive_fails", "mail")),
        db_path=db_path,
        retryable_status_codes=tuple(int(c) for c in _strict(raw, "retryable_status_codes", "mail")),
    )


def _parse_gmail_variations(raw: dict) -> GmailVariationsConfig:
    return _parse_section_strict(GmailVariationsConfig, raw, "gmail_variations")


_CONFIG_DIR_NAME = "config"
_CONFIG_FILES = (
    "config.yaml",
    "logging.yaml",
    "mail.yaml",
    "captcha.yaml",
    # Per-service configs
    "elevenlabs.yaml",
    "openrouter.yaml",
    "chatgpt.yaml",
    "leonardo.yaml",
    "klingai.yaml",
    "twoslides.yaml",
    "testmail.yaml",
    "artificialanalysis.yaml",
    "sentry.yaml",
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


def load_config(path: Path | None = None) -> AppConfig:
    """Load config từ config/*.yaml -> AppConfig. Ném lỗi nếu config không load được."""
    if path is None:
        base_dir = Path(__file__).parent.parent.parent
    else:
        # path có thể là file hoặc folder: nếu là file thì lấy parent của parent (project root)
        base_dir = path.parent if path.is_dir() else path.parent.parent if path.parent.name == _CONFIG_DIR_NAME else path.parent
    raw = _load_raw(base_dir)
    db_path = base_dir / "data" / "accounts.db"
    from common.database import init_db
    init_db(db_path)
    browser_raw = _require_section(raw, "browser")
    return AppConfig(
        log=_parse_log(_require_section(raw, "log")),
        headless=_strict(browser_raw, "headless", "browser"),
        viewport_width=_strict(browser_raw, "viewport_width", "browser"),
        viewport_height=_strict(browser_raw, "viewport_height", "browser"),
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
        twoslides=_parse_section_strict(TwoSlidesConfig, _require_section(raw, "twoslides"), "twoslides"),
        testmail=_parse_section_strict(TestmailConfig, _require_section(raw, "testmail"), "testmail"),
        mail=_parse_mail(_require_section(raw, "mail"), db_path),
        auth_sync=_parse_auth_sync(_require_section(raw, "auth_sync")),
        cliproxy_sync=_parse_cliproxy_sync(_require_section(raw, "cliproxy_sync")),
        sentry=_parse_section_strict(SentryConfig, _require_section(raw, "sentry"), "sentry"),
        proxy=_parse_proxy(raw.get("proxy", {})),
        base_dir=base_dir,
    )
