# registrar

Browser automation toolkit — tự động đăng ký tài khoản trên các AI/SaaS platform.

> Runtime note: root orchestration publishes `registrar` on port `8709`. Older service-local examples that mention `8799` are legacy local-dev references and must not be used as platform runtime truth.

**Stack**: FastAPI · Playwright/Camoufox · SQLAlchemy · asyncio concurrent jobs

## Setup

```powershell
.\setup.ps1
```

## Run

```bash
# API backend (port 8799)
python run_api.py

# CLI menu
python main.py

# Dev all-in-one (kill ports + start all services)
dev.cmd
```

## Services supported

| Key | Platform |
|-----|----------|
| `OPENROUTER` | openrouter.ai |
| `CHATGPT` | chatgpt.com |
| `ELEVENLABS` | elevenlabs.io |
| `LEONARDO` | leonardo.ai |
| `KLINGAI` | klingai.com |
| `ARTIFICIALANALYSIS` | artificialanalysis.ai |
| `TESTMAIL` | testmail.app |

## API Endpoints

### Registration `POST /api/v1/registration/`

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/services` | Liệt kê services khả dụng |
| POST | `/jobs` | Start registration job |
| GET | `/jobs` | List tất cả jobs |
| GET | `/jobs/{job_id}` | Job status + progress |
| POST | `/jobs/{job_id}/cancel` | Cancel job |
| WS | `/jobs/{job_id}/logs` | Stream logs real-time |

### Accounts `GET /api/v1/accounts/`

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/` | List accounts (filter by service) |
| POST | `/add` | Add account thủ công |
| POST | `/check` | Check account status |
| POST | `/check-all` | Bulk check |

### Config `GET /api/v1/config/`

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/files` | List config files |
| GET | `/raw?file=X` | Đọc raw YAML |
| PUT | `/raw?file=X` | Ghi YAML |

## Structure

```
src/
  api/          ← FastAPI routes, schemas, websocket
  services/     ← registrar per platform (9 services)
  mail/         ← mail provider clients
  core/         ← browser, database, errors, session, guard
  captcha/      ← capsolver, patchright
  checkers/     ← account validators
  cli/          ← CLI menu
ui/             ← Frontend (Vite + React + Tauri)
config/         ← 13 YAML configs per service
```

## Docs

See [docs/](docs/).
