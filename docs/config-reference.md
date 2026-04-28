# Config Reference

Runtime configuration is split across multiple YAML files in `config/`. Each file
maps to a section in `AppConfig` (frozen dataclasses in `src/config/settings.py`).

> Mail provider lists are **no longer in YAML** — they live in SQLite (`data/accounts.db`)
> and are managed via the UI Providers page or `src/core/database.py`.

---

## `log`

| Key | Type | Default | Description |
|---|---|---|---|
| `append` | bool | `false` | `false` clears `debug/run.log` on each run; `true` appends to the existing log |

---

## `browser`

| Key | Type | Default | Description |
|---|---|---|---|
| `headless` | bool | `false` | `false` shows the browser window; `true` runs headless |

---

## `timeouts`

Maps to `TimeoutConfig`.
All values are in seconds unless the name or description says `ms`.

| Key | Type | Default | Unit | Description |
|---|---|---|---|---|
| `email_wait` | int | `120` | sec | Maximum wait for verification email |
| `page_load` | int | `15000` | ms | Page load timeout |
| `poll_interval` | int | `4` | sec | Inbox poll interval |
| `step_delay` | int | `1500` | ms | Delay between onboarding steps |
| `click_delay` | int | `500` | ms | Delay after click |
| `short_delay` | int | `300` | ms | Short delay for fill/toggle actions |
| `nav_delay` | int | `2000` | ms | Delay after navigation |
| `sign_in_delay` | int | `3000` | ms | Delay after sign-in submit |
| `batch_delay_sec` | int | `5` | sec | Delay between accounts in batch mode |

---

## `llm`

Maps to `LLMConfig`.
Used by the ElevenLabs captcha solver and related integration tests.

| Key | Type | Default | Description |
|---|---|---|---|
| `base_url` | str | `http://localhost:8317/v1` | Base URL of the OpenAI-compatible LLM server |
| `api_key` | str | `ccs-internal-managed` | API key sent to the LLM server |
| `model` | str | `gpt-5.4` | Model name used for requests |
| `max_tokens` | int | `256` | Max tokens for click-detection responses |
| `verify_max_tokens` | int | `64` | Max tokens for verify-button detection |

The LLM server must support image input via the Chat Completions API.

---

## `captcha`

Maps to `CaptchaConfig`.
These values control the pacing and thresholds of the ElevenLabs captcha solver.

| Key | Type | Default | Unit | Description |
|---|---|---|---|---|
| `max_rounds` | int | `10` | rounds | Maximum solve rounds before giving up |
| `checkbox_wait_sec` | int | `12` | sec | Max wait for the challenge after clicking the checkbox |
| `challenge_poll_ms` | int | `1000` | ms | Poll interval while waiting for the challenge |
| `challenge_min_w` | int | `300` | px | Minimum challenge iframe width |
| `challenge_min_h` | int | `250` | px | Minimum challenge iframe height |
| `click_delay_ms` | int | `400` | ms | Delay between image clicks |
| `post_click_wait_ms` | int | `600` | ms | Wait after clicks before locating verify |
| `post_verify_wait_ms` | int | `2500` | ms | Wait after clicking Verify/Next |
| `recheck_wait_ms` | int | `3000` | ms | Extra wait before confirming the challenge is gone |
| `pre_solve_wait_ms` | int | `600` | ms | Wait before taking the challenge screenshot |
| `drag_steps` | int | `20` | steps | Intermediate drag steps |
| `drag_settle_ms` | int | `400` | ms | Wait after drag completes |

---

## `elevenlabs`

Maps to `ElevenLabsConfig`.

| Key | Type | Default | Description |
|---|---|---|---|
| `signup_url` | str | `https://elevenlabs.io/app/sign-up` | ElevenLabs sign-up page |
| `api_keys_url` | str | `https://elevenlabs.io/app/developers/api-keys` | ElevenLabs API keys page |
| `app_base_url` | str | `elevenlabs.io/app` | Substring used to detect the app/dashboard |
| `captcha_load_wait_ms` | int | `4000` | Wait after clicking Sign Up before captcha handling |

---

## `chatgpt`

Maps to `ChatGPTConfig`.
Controls the OAuth PKCE signup and callback flow.

| Key | Type | Default | Description |
|---|---|---|---|
| `oauth_authorize_url` | str | `https://auth.openai.com/oauth/authorize` | OAuth authorization endpoint |
| `oauth_token_url` | str | `https://auth.openai.com/oauth/token` | OAuth token endpoint |
| `client_id` | str | `app_EMoamEEZ73f0CkXaXp7hrann` | Client ID used by the Codex-compatible auth flow |
| `redirect_uri` | str | `http://localhost:1455/auth/callback` | Local callback URL |
| `callback_port` | int | `1455` | Port used by the local callback server |
| `otp_wait_sec` | int | `90` | Max wait for OTP email |
| `otp_poll_interval` | int | `4` | OTP inbox poll interval |
| `post_submit_wait_ms` | int | `3000` | Wait after each form submit |
| `callback_timeout_sec` | int | `300` | Max wait for OAuth callback |

---

## `leonardo`

Maps to `LeonardoConfig`.
Controls the Leonardo AI email login/signup flow.

| Key | Type | Default | Description |
|---|---|---|---|
| `login_url` | str | `https://app.leonardo.ai/auth/login` | Leonardo auth page |
| `app_url_contains` | str | `app.leonardo.ai` | Substring used to detect Leonardo app/dashboard |
| `verification_sender` | str | `leonardo.ai` | Sender/domain filter used when polling the verification email |
| `otp_wait_sec` | int | `180` | Max wait for Leonardo verification email |
| `otp_poll_interval` | int | `4` | Poll interval for Leonardo verification email |
| `post_submit_wait_ms` | int | `3000` | Wait after Leonardo form submits |
| `turnstile_timeout_sec` | int | `300` | Max wait for manual Turnstile completion |

---

## `artificialanalysis`

Maps to `ArtificialAnalysisConfig`.
Controls the Artificial Analysis magic link auth flow.

| Key | Type | Default | Description |
|---|---|---|---|
| `login_url` | str | `https://artificialanalysis.ai/login` | Login/signup page |
| `app_url_contains` | str | `artificialanalysis.ai` | Substring used to detect the app |
| `magic_link_wait_sec` | int | `120` | Max wait for magic link email |
| `post_submit_wait_ms` | int | `3000` | Wait after submitting email |

---

## `auth_sync`

Maps to `AuthSyncConfig`.
Controls syncing exported Codex auth files from this repo's `auth/` folder to an external auth directory.

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Enable automatic sync when Codex auth is exported |
| `target_dir` | str | `C:\Users\admin\.ccs\cliproxy\auth` | External auth directory watched by CCS / CLIProxyAPI |

---

## `mail`

Maps to `MailConfig`. Provider lists are stored in **SQLite DB**, not YAML.

| Key | Type | Default | Description |
|---|---|---|---|
| `cooldown_sec` | int | `120` | Cooldown after a provider failure before reuse |
| `max_consecutive_fails` | int | `3` | Disable provider after this many consecutive failures |

Providers are managed in `data/accounts.db` (`mail_providers` table).
Each provider has a `type` (`mail.tm`, `mailslurp`, `testmail`), `api_key`, and
`provider_domain_tags` entries that control which services can use it.

Tag `any` means the provider serves all services. Specific tags (e.g. `chatgpt`, `elevenlabs`)
limit the provider to those services only.

---

## `testmail`

Maps to `TestmailConfig`. Controls OTP polling when testmail.app is used as inbox provider.

| Key | Type | Default | Description |
|---|---|---|---|
| `otp_wait_sec` | int | `90` | Max wait for OTP/verification email |
| `otp_poll_interval` | int | `5` | Poll interval |
| `max_retries` | int | `3` | Max retries on transient errors |

---

## `openrouter`

Maps to `OpenRouterConfig`.

| Key | Type | Default | Description |
|---|---|---|---|
| `signup_url` | str | `https://openrouter.ai/sign-up` | Sign-up page |
| `keys_url` | str | `https://openrouter.ai/settings/keys` | API keys page |
| `app_url_contains` | str | `openrouter.ai` | Substring to detect app/dashboard |
| `otp_wait_sec` | int | `90` | Max wait for verification email |
| `otp_poll_interval` | int | `5` | Poll interval |
| `post_submit_wait_ms` | int | `3000` | Wait after form submits |

---

## `klingai`

Maps to `KlingAIConfig`.

| Key | Type | Default | Description |
|---|---|---|---|
| `signup_url` | str | `https://klingai.com` | Home / landing page |
| `app_url_contains` | str | `klingai.com` | Substring to detect app |
| `otp_wait_sec` | int | `120` | Max wait for OTP email |
| `otp_poll_interval` | int | `5` | Poll interval |
| `post_submit_wait_ms` | int | `3000` | Wait after form submits |

---

## Example configs

### `config/mail.yaml`
```yaml
mail:
  cooldown_sec: 120
  max_consecutive_fails: 3
  # providers are in DB, not here
```

### `config/testmail.yaml`
```yaml
testmail:
  otp_wait_sec: 90
  otp_poll_interval: 5
  max_retries: 3
```

### `config/chatgpt.yaml`
```yaml
chatgpt:
  oauth_authorize_url: "https://auth.openai.com/oauth/authorize"
  oauth_token_url: "https://auth.openai.com/oauth/token"
  client_id: "app_EMoamEEZ73f0CkXaXp7hrann"
  redirect_uri: "http://localhost:1455/auth/callback"
  callback_port: 1455
  otp_wait_sec: 90
  otp_poll_interval: 4
  post_submit_wait_ms: 3000
  callback_timeout_sec: 300
```

### `config/browser.yaml` (merged into root config)
```yaml
browser:
  headless: false
  viewport_width: 1280
  viewport_height: 720
```

---

## Derived Paths

`AppConfig` also exposes these derived paths:

| Property | Value |
|---|---|
| `screenshot_dir` | `<base_dir>/screenshots/` |
| `debug_dir` | `<base_dir>/debug/` |
| `log_file` | `<base_dir>/debug/run.log` |

`base_dir` defaults to the project root.
