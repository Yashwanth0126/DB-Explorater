# Deploying to Render

This backend deploys to Render as a **Docker web service** backed by **Render's
managed Postgres** (switching off SQLite is just one env var — the code doesn't change).

There are two ways to do this: the one-click Blueprint (`render.yaml`, included in
this repo) or manual setup through the dashboard. The Blueprint is faster.

---

## Option A — Blueprint deploy (recommended)

1. **Push this project to a GitHub repo** (make sure `.env` is NOT committed —
   it's already gitignored).

2. In the Render dashboard: **New → Blueprint**, then connect your repo. Render
   will read `render.yaml` and propose:
   - a **web service** (`credential-rotation-backend`) built from the `Dockerfile`
   - a **managed Postgres database** (`credential-rotation-db`)

3. Render auto-wires `DATABASE_URL` from the database to the web service, and
   auto-generates `JWT_SECRET_KEY`. You still need to manually set a few values
   marked `sync: false` in `render.yaml` — Render will prompt you for these during
   the Blueprint setup, or you can set them after in **Environment**:
   - `ENCRYPTION_KEY` — generate locally first:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
     **Do not lose this key** — it decrypts every stored credential. If you rotate
     it, all previously-stored encrypted passwords become unreadable.
   - `ADMIN_PASSWORD` — the login password for the API's default admin account
   - `ADMIN_EMAIL`
   - `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` — only needed if you flip
     `NOTIFICATIONS_ENABLED` to `true`

4. Click **Apply**. Render builds the Docker image and deploys.

5. Once live, check `https://<your-service>.onrender.com/health` → `{"status":"ok"}`.

That's it — tables are created automatically on first startup (`Base.metadata.create_all`),
same as local dev, just against the Postgres Render provisioned instead of SQLite.

---

## Option B — Manual setup (no Blueprint)

1. **New → PostgreSQL** in Render. Note the **Internal Database URL** it gives you
   (starts with `postgresql://...`).

2. **New → Web Service** → connect your repo → Render detects the `Dockerfile`
   automatically (or set **Runtime: Docker** manually).

3. Under **Environment**, add these variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Internal Database URL from step 1 |
   | `JWT_SECRET_KEY` | `openssl rand -hex 32` output |
   | `JWT_ALGORITHM` | `HS256` |
   | `JWT_EXPIRE_MINUTES` | `60` |
   | `ENCRYPTION_KEY` | Fernet key (see command above) |
   | `ADMIN_USERNAME` | `admin` (or your choice) |
   | `ADMIN_PASSWORD` | your choice — not the default |
   | `ADMIN_EMAIL` | your email |
   | `SCHEDULER_INTERVAL_MINUTES` | `60` |
   | `NOTIFICATIONS_ENABLED` | `false` to start |
   | `ENV` | `production` |

4. Set **Health Check Path** to `/health`.

5. Deploy.

---

## After deploying: switching your control DB from SQLite to Postgres

You don't need to do anything code-side — `app/database.py` already branches on the
`DATABASE_URL` scheme:

```python
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
```

Locally, `DATABASE_URL=sqlite:///./credential_rotation.db`.
On Render, `DATABASE_URL` is a `postgresql://...` connection string — SQLAlchemy
and `psycopg2` handle the rest. Same models, same migrations-on-startup behavior,
different backing store.

If you later add real schema migrations (e.g. with Alembic) instead of relying on
`create_all`, that's the natural next step once the schema stabilizes — not required
for the hackathon stage.

## Verifying the deployed API

```bash
curl https://<your-service>.onrender.com/health

curl -X POST https://<your-service>.onrender.com/auth/login \
  -d "username=admin&password=<your ADMIN_PASSWORD>" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

You should get back a JWT. From there, everything documented in `SETUP.md` step 7
works identically against the deployed URL instead of `localhost:8000`.

## Notes on Render's free tier

- Free web services spin down after inactivity and cold-start on the next request —
  fine for a hackathon demo, but the background scheduler won't fire while the
  service is asleep. For a live "credentials rotate automatically on schedule" demo,
  either keep the service warm (a paid plan, or an external uptime pinger) or trigger
  rotation manually via `POST /rotation/{id}/rotate-now` during the demo.
- Free Postgres databases on Render expire after a set period (currently 30 days) —
  fine for hackathon judging, not for anything you need to keep long-term.
