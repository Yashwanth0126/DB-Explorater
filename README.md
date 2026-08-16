# Credential Rotation System — Backend

Automated database credential rotation: detects expiring passwords, notifies
stakeholders, generates and applies a new password on the target database,
propagates it to consuming applications, verifies the new connection works, and
logs everything. Rule-based (no ML) — see `app/services/rule_engine.py`.

- **Local setup & run:** see [`SETUP.md`](./SETUP.md)
- **Deploy to Render:** see [`DEPLOY.md`](./DEPLOY.md)
- **Interactive API docs:** `/docs` once running (Swagger UI)

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + Python |
| Control DB | SQLite locally → PostgreSQL in the cloud (same code, one env var) |
| Scheduler | APScheduler |
| Secret storage | Fernet-encrypted column in the control DB (Vault-style interface, swappable later) |
| Notifications | SMTP |
| Auth | JWT |
| Deployment | Docker → Render |

## Project layout

```
app/
  main.py                 FastAPI app, startup, scheduler lifecycle
  config.py                Env-driven settings
  database.py               SQLAlchemy engine/session (sqlite or postgres via DATABASE_URL)
  models.py                    All ORM tables
  schemas.py                     Pydantic request/response models
  security.py                      JWT auth + password hashing
  crypto.py                         Fernet encrypt/decrypt for secrets at rest
  scheduler.py                       APScheduler job: periodic expiry check
  routers/
    auth.py                            Login
    policies.py                        Rotation policy CRUD
    databases.py                       Target database CRUD + computed status
    applications.py                    Applications that consume rotated creds
    stakeholders.py                    Who gets notified per database
    rotation.py                        Manual rotate-now / evaluate-now / history
    dashboard.py                       Summary counts + status table
    audit.py                           Audit log + notification history
    secrets.py                         Application-facing "pull my current credential" endpoint
  services/
    rule_engine.py                     Core decision logic + rotation orchestration
    rotation_engine.py                 Generates + applies new Postgres passwords
    secret_manager.py                  Encrypted credential storage/retrieval
    notification_service.py            SMTP email sending
    audit_logger.py                    Writes audit log entries
```

## The core rule (no ML, just this)

```
days_remaining > notify_before_days   → no action
days_remaining <= notify_before_days  → notify stakeholders
auto_rotate enabled on that database  → rotate automatically, propagate, verify, log
```

## What "automatic propagation" actually means here

1. Rotation engine connects as an admin/superuser and runs `ALTER USER ... PASSWORD`
   on the target Postgres user.
2. The new password is immediately test-connected before anything else happens —
   if it can't connect, the whole rotation is marked failed and stakeholders are
   alerted instead of silently leaving a broken credential in place.
3. The new password is encrypted and stored as the active credential.
4. Any application registered against that database with a `webhook_url` gets a
   POST ping so it can reload immediately.
5. Any application can also just pull the live credential anytime via
   `GET /secrets/current` with its `X-Api-Key` header — no polling logic needed on
   the app side, it always gets whatever is currently active.
