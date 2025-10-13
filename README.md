# Telescope Project (Canary)

An open-source web UI and control stack for an automatic tracking telescope and small planetarium. The repository contains a Flask web application, plate-solver helpers, camera control utilities, and a client-side planetarium view.

## Repository layout (important locations)

- `Server.py` — main Flask entrypoint used for local development.
- `WebsocketServer.py` — WebSocket server logic for live camera feeds and commands.
- `controllers/` — Flask blueprints: pages and API endpoints (including the star map controller).
- `templates/` — Jinja2 templates; star map is `templates/star_map.html`.
- `static/` — Frontend assets (CSS, JS). The planetarium renderer is in `static/js/star_map.js`.
- `models/` — SQLAlchemy models and DB helpers.
- `instance/` — Instance-specific runtime files (`Data.db`, optional `.env`).
- `infrastructure/` — Deployment artifacts (Caddy binary, cloudflared, `config.yml`).
- `algorithms/` and `algorithms2.py` — Astronomy and conversion utilities.
- `utility/` — Helper scripts and `requirements.txt`.

## Quickstart (development)

Prereqs: Python 3.11+, Git, optional tools (Caddy/cloudflared) for local tunnelling.

1. Activate the virtual environment (Windows PowerShell example):

```powershell
.\.venv\bin\Activate.ps1
pip install -r utility\requirements.txt
```

2. Create an `instance/.env` with required variables (do not commit):

```text
FLASK_SECRET_KEY=replace-with-a-strong-secret
MAIL_USERNAME=you@example.com
MAIL_PASSWORD=super-secret
ENCRYPTION_KEY=some-random-key
SQLALCHEMY_TRACK_MODIFICATIONS=False
EXECUTER=your-windows-username
```

3. Run the server from project root:

```powershell
python Server.py
```

The app will try to start optional infrastructure binaries (Caddy and cloudflared) from `infrastructure/` when configured to do so. If you do not want those started locally, set `ifOnline` to false

## Configuration

- The app loads `instance/.env` (if present).
- Database: SQLite DB file is `instance/Data.db` by default. `Server.py` sets `SQLALCHEMY_DATABASE_URI` accordingly.
- Email: configured in `Server.py`

## Infrastructure and deployment files

You moved the infrastructure artifacts into `infrastructure/` — good call. Keep these files out of the repo if they contain sensitive data.

If you move them again, update `Server.py` paths (already configured to use `infrastructure/`). On production, prefer host-installed or containerized Caddy/cloudflared instead of keeping binaries in the repo.

## Development tips

- To reduce noise and accidental commits, do not keep `venv/` in the repository; prefer `.venv` ignored by `.gitignore`.
- Use `pip freeze > utility/requirements.txt` when updating dependencies.
- If you refactor Python modules (e.g., move `algorithms2.py` into `algorithms/`), update imports (or expose functions via `algorithms/__init__.py`).

## Troubleshooting

- `.env not found`: verify `instance/.env` exists or use system env vars.
- Caddy/cloudflared fail to start: check `infrastructure/` paths, file permissions, and `infrastructure/config.yml` contents.
- Planetarium UI broken: open browser DevTools; `static/js/star_map.js` logs helpful debug messages.

## Google Docs project file:

- https://docs.google.com/document/d/1ntlr__WV3JdlY7PkM1GIIkk02cW5x_GakHwJQ8XlgZw/

