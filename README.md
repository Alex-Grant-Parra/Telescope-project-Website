# Rpi5 Telescope Client

This project is telescope client for ASTRA.

It connects your telescope hardware to the remote server, receives commands over WebSocket, sends live camera frames, tracks telescope state, and uploads captured photos.

Master website/server repo: https://github.com/Alex-Grant-Parra/ASTRA

## Required setup

Before running, fill these required values in `config/client_profile.json`:

- `client_config.client_id`
- `client_config.base_url` (example: `https://telescopes.dev/`)
- `client_config.api_token`

Set up a venv:

- `python -m venv venv`

And finally install packages

- `pip install -r requirements.txt`

## Run

```bash
python Client.py
```

Optional interactive setup:

```bash
python Client.py setup
```
