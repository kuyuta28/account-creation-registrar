# registrar

Core service — tự động đăng ký tài khoản trên các AI/SaaS platform.

> Runtime note: root orchestration publishes `registrar` on port `8709`. Older service-local examples that mention `8799` are legacy local-dev references and must not be used as platform runtime truth.

## Run

```bash
python run_api.py        # FastAPI backend (port 8799)
python run_tts.py        # TTS proxy (port 8800)
python main.py           # CLI menu
```

## Docs

- [api-reference.md](api-reference.md) — REST API endpoints
- [config-reference.md](config-reference.md) — YAML config per service
- [captcha-solver.md](captcha-solver.md) — captcha handling
- [nopecha-research.md](nopecha-research.md) — NopeCHA research notes
- [scripts.md](scripts.md) — utility scripts
- [testing.md](testing.md) — test strategy
- [troubleshooting.md](troubleshooting.md) — common issues
- [modules/](modules/) — per-module docs
