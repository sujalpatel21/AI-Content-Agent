# Workflow: Postiz Deployment (Publishing Backend)

## Objective
Stand up a self-hosted Postiz instance (https://github.com/gitroomhq/postiz-app) to handle actual publishing/scheduling to social platforms. This repo's tools generate drafts; Postiz is where a draft becomes a scheduled or published post.

This is infrastructure, not application code — it does not live inside this repo. This doc exists so whoever has terminal access to the target server can run the deployment correctly, and so this repo's tools know what to expect once it's up.

## Before you start: resource reality check
The official `docker-compose.yaml` in `gitroomhq/postiz-app` brings up **8 containers**, not one:
- `postiz` (the app itself)
- `postiz-postgres`, `postiz-redis` (Postiz's own state)
- `temporal`, `temporal-postgresql`, `temporal-elasticsearch`, `temporal-ui`, `temporal-admin-tools` (Temporal is a core dependency per Postiz's own tech stack list, not optional — it handles scheduled post execution)

Elasticsearch alone typically needs 2GB+ RAM on its own. **Recommend 4-8GB RAM minimum for the VPS this runs on.** If Benji's VPS is a small/cheap instance already running WhatsApp automation, putting this stack on the same box risks starving both. Decide before deploying: same VPS as Benji, or a separate host sized for this.

## Required Inputs (must decide/obtain before running)
1. **A domain or subdomain pointing at the target server**, with HTTPS. `FRONTEND_URL`/`NEXT_PUBLIC_BACKEND_URL` must be the real public URL Postiz is reached on — most platform OAuth flows (LinkedIn, Meta, etc.) reject bare IP:port callback URLs. A reverse proxy (Caddy/nginx/Traefik) terminating TLS in front of the `postiz` container is the standard setup; the compose file itself does not include one.
2. **A generated `JWT_SECRET`** — treat as a real secret, not a placeholder. Generate with e.g. `openssl rand -hex 32` on the server at deploy time; don't reuse a value from any doc or chat.
3. **Per-platform developer app credentials**, one pair of client ID/secret per platform you actually want to connect — only fill in what you're using at launch, leave the rest blank:
   - `FACEBOOK_APP_ID` / `FACEBOOK_APP_SECRET` (also covers Instagram via the same Meta app)
   - `THREADS_APP_ID` / `THREADS_APP_SECRET`
   - `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET`
   - `X_API_KEY` / `X_API_SECRET`
   - Others (`TIKTOK_*`, `PINTEREST_*`, `REDDIT_*`, `DISCORD_*`, etc.) only as needed later
   - These require you to register a developer app on each platform yourself — this repo/session cannot create them, and some (Meta, TikTok) involve an app-review process that takes real time, not just signup.
4. **Storage**: `STORAGE_PROVIDER=local` works to get started (default in the compose file). Postiz's own `.env.example` says Cloudflare R2 is "currently required to save things like social media avatars" — unclear if that's a hard requirement or a degraded-feature note. Start with local; revisit if avatar-related features misbehave.

## Steps
1. On the target server: `git clone https://github.com/gitroomhq/postiz-app`
2. Edit the `postiz` service's `environment` block in `docker-compose.yaml`:
   - Set `MAIN_URL`, `FRONTEND_URL`, `NEXT_PUBLIC_BACKEND_URL` to the real public URL (see Required Inputs #1)
   - Set `JWT_SECRET` to a freshly generated value
   - Fill in only the platform credentials you have ready
3. Put a reverse proxy in front of it for TLS if one isn't already handled at the infra level
4. `docker compose up -d`
5. Watch `docker compose logs -f postiz` for startup errors before assuming it's healthy — the healthchecks on postgres/redis gate startup, but Temporal's stack has more moving parts and can fail quietly
6. Visit the public URL, create the admin account (first registration becomes the account, per Postiz's default `DISABLE_REGISTRATION=false` — consider setting this to `true` after the first account exists, so the instance isn't open to anyone who finds the URL)
7. Connect each social channel from the Postiz UI (this is where each platform's OAuth flow actually runs)
8. Generate a Postiz API key from its dashboard for programmatic access

## Connecting back to this repo
Once Postiz is live and has an API key:
- Set `POSTIZ_API_URL` and `POSTIZ_API_KEY` in this repo's `.env` (not yet consumed by any tool here — the publish step that calls Postiz's API hasn't been built yet; this is groundwork for it)
- Postiz ships an official n8n node (`n8n-nodes-postiz`) — n8n workflows should use that node directly rather than raw HTTP Request nodes against Postiz's API
- Use `type: "draft"` on Postiz's create-post API/node for anything that needs human approval before publishing — see `workflows/post_generator.md` for why that gate matters here

## Known Risk (flagged in an earlier conversation, still open)
Postiz has a documented bug scheduling X/Twitter threads via the API — the first tweet publishes but follow-up tweets in the thread sometimes don't, and `https://` URLs get stripped from thread content ([gitroomhq/postiz-app#1581](https://github.com/gitroomhq/postiz-app/issues/1581)). Don't trust automated X-thread publishing unattended until this is confirmed fixed or worked around.

## Who does the deployment
This session has no SSH/terminal access to any VPS — only to Anthropic-managed cloud environments. Someone with terminal access to the target server needs to run steps 1-6, or grant this kind of access to a session that can.
