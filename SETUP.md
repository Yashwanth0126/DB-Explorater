# Local Setup — Credential Rotation Backend

This runs the backend locally with **SQLite** (zero setup, no separate database server
needed). When you're ready for the cloud, you swap one env var to point at Postgres —
nothing else in the code changes.

## 1. Requirements

- Python 3.11+
- pip

## 2. Clone / open the project

```bash
cd credential-rotation-backend
```

## 3. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
```

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 5. Configure environment variables

```bash
cp .env.example .env
```

Now open `.env` and set two required secrets:

**JWT secret** (any random string works, or generate one):
```bash
openssl rand -hex 32
```
Paste it into `JWT_SECRET_KEY`.

**Encryption key** (used to encrypt stored DB passwords at rest — required, the app
will refuse to start without it):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste it into `ENCRYPTION_KEY`.

Leave `DATABASE_URL` as the default SQLite value:
```
DATABASE_URL=sqlite:///./credential_rotation.db
```

Also set your own login for the dashboard:
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=pick_something_not_the_default
```

Notifications default to **off** (`NOTIFICATIONS_ENABLED=false`) — emails are logged
to the console instead of actually sent, so you don't need SMTP configured to test
the flow. Flip it to `true` and fill in `SMTP_*` when you want real emails.

## 6. Run it

```bash
uvicorn app.main:app --reload
```

On first startup the app will:
- create all tables in `credential_rotation.db`
- create your admin user
- start the background scheduler (checks all databases every `SCHEDULER_INTERVAL_MINUTES`, default 60)

Visit **http://localhost:8000/docs** for interactive Swagger docs — this is the
easiest way to exercise every endpoint without a frontend.

## 7. Try the flow end-to-end

1. **Log in** — `POST /auth/login` with your `ADMIN_USERNAME` / `ADMIN_PASSWORD`
   (form-encoded, not JSON — Swagger's "Authorize" button handles this for you).
   Copy the `access_token`.
2. **Create a rotation policy** — `POST /policies`
   ```json
   { "name": "default-30d", "rotation_interval_days": 30, "notify_before_days": 7, "auto_rotate": true }
   ```
3. **Register a target database** — `POST /databases`. This needs real Postgres
   credentials if you want actual rotation to succeed (a superuser/admin login that's
   allowed to run `ALTER USER`, plus the app-facing user whose password gets rotated).
   If you just want to see the notify/audit/dashboard flow without a real Postgres
   instance, you can still create the record — rotation attempts will simply fail
   with a clear connection error, which is itself useful to see (check
   `GET /rotation/{id}/history`).
4. **Add a stakeholder** — `POST /stakeholders` — who gets notified.
5. **Register an application** — `POST /applications` — this generates an `api_key`
   the application uses to pull its credential from `GET /secrets/current`
   (header `X-Api-Key: <key>`).
6. **Check the dashboard** — `GET /dashboard/summary` and `GET /dashboard/table`.
7. **Force an evaluation now** instead of waiting for the scheduler —
   `POST /rotation/{database_id}/evaluate` (runs the same day-count rule the
   scheduler runs) or `POST /rotation/{database_id}/rotate-now` (rotates immediately,
   ignoring the day-count threshold).
8. **Check history / notifications / audit** —
   `GET /rotation/{database_id}/history`, `GET /audit/notifications`, `GET /audit/logs`.

## Testing against a real local Postgres (optional)

If you want to test actual password rotation, spin up a throwaway Postgres with Docker:

```bash
docker run --name test-pg -e POSTGRES_PASSWORD=adminpass -p 5432:5432 -d postgres:16
docker exec -it test-pg psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'initial_pw';"
```

Then register it as a target database with:
- `host: localhost`, `port: 5432`, `db_name: postgres`
- `admin_username: postgres`, `admin_password: adminpass`
- `target_username: app_user`, `target_password: initial_pw`

Now `POST /rotation/{id}/rotate-now` will actually connect, run `ALTER USER`, verify
the new password by reconnecting with it, and store it encrypted.

## Notes

- **Never commit `.env`** — it's already in `.gitignore`.
- SQLite is fine for local dev and demos, but it's a single file with no concurrent
  write support — don't use it in production. See `DEPLOY.md` for switching to
  Postgres on Render.
