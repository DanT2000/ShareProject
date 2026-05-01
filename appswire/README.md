# AppsWire

Self-hosted portal for showcasing your apps, tools, and utilities.

## Quick Start

```bash
git clone <repo>
cd appswire
docker compose up -d --build
```

- Public site: http://localhost:8090
- Admin panel: http://localhost:8090/admin

## First Run

On the first visit to `/admin`, you'll be prompted to create an administrator password (min 8 characters). After that, the setup page is replaced by a standard login form.

## Data Storage

All data is stored in `./storage/`:

| Path | Contents |
|---|---|
| `storage/appswire.db` | SQLite database (projects, actions, settings, password hash) |
| `storage/projects/<id>/` | Project files and images |

**Backup:**
```bash
cp -r storage/ storage_backup_$(date +%Y%m%d)/
```

## Docker Compose Volume

The `docker-compose.yml` mounts `./storage` into the container so data persists across restarts and rebuilds.

## Deploy on Coolify

| Setting | Value |
|---|---|
| Build Pack | `Dockerfile` |
| Base Directory | `/` |
| Dockerfile Location | `/Dockerfile` |
| Port Exposes | `8090` |
| Persistent Storage | `/app/storage` |
| Domain | your domain (e.g. `https://appswire.example.com`) |

If HTTPS is terminated by a reverse proxy upstream, set the domain as `http://` inside Coolify.

## Environment Variables

No `.env` is required. The app is fully self-contained:
- Secret key is auto-generated on first run and stored in the database.
- Admin password is set via the web UI on first visit to `/admin`.

Optional overrides (not needed in normal use):

| Variable | Default | Description |
|---|---|---|
| `STORAGE_PATH` | `<project_root>/storage` | Override storage directory |
