# Enterprise Standards — registrar

> **Phần lớn đã chuẩn hóa trong [docs/ENTERPRISE-STANDARDS.md](../../docs/ENTERPRISE-STANDARDS.md).**
> File này chỉ ghi những đặc thù riêng của registrar.

---

## Registrar-Specific Standards

### Service Interface

```python
async def register_xxx(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> Optional[AccountRecord]:
```

### Service Registry

Services are registered in `src/services/registry.py`.

### Database Tables

| Table | Purpose |
|-------|---------|
| `accounts` | Main account storage |
| `mailbox_service_blocks` | Prevent email reuse |
| `jobs` | Registration job tracking |

### Testing

Registrar has additional integration test requirements:
- Full flow với DB
- Mock external services (Google, etc.)
- Browser automation với Playwright
