# Free hosting: Render + Neon Postgres + your GoDaddy domain

This gets the app live at `https://yourdomain.com` for free: Render hosts the
app itself (API + built frontend, one service), Neon hosts a small Postgres
database for accounts and saved tournaments (so they survive Render's
ephemeral-disk restarts).

## 1. Create the Neon database

1. Sign up free at neon.tech (no card required).
2. **Create a project** (any name/region).
3. On the project dashboard, click **Connect** and copy the connection
   string — looks like:
   `postgresql://user:password@ep-xxxxx.neon.tech/dbname?sslmode=require`
4. Keep this handy — you'll paste it into both your local `.env` and Render's
   environment variables.

Tables are created automatically the first time the app starts (see
`engine/db.py::init_db`, called on FastAPI startup) — no manual SQL needed.

## 2. Test locally first

```powershell
cd cricket_sim
copy .env.example .env
# edit .env, paste your Neon connection string as DATABASE_URL

pip install -r requirements_web.txt
cd frontend
npm install
npm run build
cd ..

python run_web.py
```

Visit `http://localhost:8000` (not the Vite dev server port) — this is the
exact production path Render will run. Register an account, play a match,
confirm things work. Check Neon's dashboard **Tables** view to confirm
`users`/`saves` rows appear.

## 3. Push the code to GitHub

Render deploys from a connected git repo. This project isn't a git repo yet:

```powershell
git init
git add .
git commit -m "Initial commit"
```

Then create a new **private** repo on github.com and follow its "push an
existing repository" instructions (`git remote add origin ...`, `git push`).

## 4. Create the Render service

1. Sign up free at render.com, connect your GitHub account.
2. **New → Web Service**, pick your repo.
3. Settings:
   - **Runtime**: Python 3
   - **Build Command**:
     `pip install -r requirements_web.txt && cd frontend && npm install && npm run build`
   - **Start Command**: `uvicorn api.app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
4. **Environment** tab → add `DATABASE_URL` = your Neon connection string.
5. Create the service. First deploy takes a few minutes (building the
   frontend too). Render gives you a `https://<something>.onrender.com` URL —
   test the whole app there before touching DNS.

Note: Render's free tier spins the service down after ~15 minutes of no
traffic, and the next request wakes it back up (30-60s cold start). Fine for
casual testing with a few people; nothing to do about it on the free tier.

## 5. Point your GoDaddy domain at it

Render → your service → **Settings → Custom Domain → Add Custom Domain**,
enter `www.yourdomain.com`. Render shows you the exact DNS record to add.
Typically:

In GoDaddy, **My Products → your domain → DNS → Manage DNS**:

| Type  | Name | Value                        |
|-------|------|-------------------------------|
| CNAME | www  | `<your-service>.onrender.com` |

For the bare domain (`yourdomain.com` with no `www`), GoDaddy doesn't support
a CNAME at the root. Easiest fix: in GoDaddy's DNS page, use **Forwarding →
Domain → Forward** to redirect `yourdomain.com` → `https://www.yourdomain.com`
(GoDaddy handles this without touching A records). Render auto-provisions a
free HTTPS certificate for `www.yourdomain.com` once DNS resolves.

## 6. Verify

- `https://www.yourdomain.com` loads over HTTPS with a valid padlock
- Refreshing on a client-side route (e.g. `/tournament`) doesn't 404
- Register/login, play a match, confirm it still shows up after the service
  has spun down and woken back up (proves Neon persistence, not local disk)

## Redeploying after a code change

Push to GitHub's `main` branch — Render auto-deploys on push (this is on by
default). No manual restart needed.
