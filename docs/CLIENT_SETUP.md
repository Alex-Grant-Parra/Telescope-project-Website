# Telescope Client Setup Guide

This guide explains how to configure and run the telescope client with the new authentication system.

## Quick Setup

### Method 1: Interactive Setup (Recommended)

Run the setup command:
```bash
python Client.py setup
```

This will prompt you to enter:
- **Client ID**: Unique identifier for your telescope (e.g., "pi-001", "telescope-main")
- **Base URL**: Server URL (e.g., "https://telescopes.dev/")
- **API Token**: Authentication token from the server administrator

The client automatically derives:
- command websocket URL: `wss://ws.<host>/`
- liveview websocket URL: `wss://liveview.<host>/`
- HTTP URL: `<base_url>`

### Method 2: Manual Configuration

Edit `config/client_profile.json` with your settings:
   ```json
   {
       "client_config": {
          "client_id": "your-unique-telescope-id",
          "base_url": "https://telescopes.dev/",
          "api_token": "your-api-token-from-server-admin"
       },
       "location": {}
   }
   ```

Static hardware/slewing settings stay in `config/client_config.json`.

## Getting an API Token

Contact your telescope server administrator to get an API token. They need to:

1. Run the token management utility on the server:
   ```bash
   python manage_tokens.py
   ```

2. Generate a new token with type "telescope" for your client

3. Provide you with the generated token (long string like: `abc123def456...`)

## Running the Client

Once configured, simply run:
```bash
python Client.py
```

The client will:
- ✅ Connect to the command WebSocket server
- ✅ Connect to the live view WebSocket server  
- ✅ Authenticate using your API token
- ✅ Start sending camera frames and handling telescope commands

## Troubleshooting

### "No API token configured"
- Run `python Client.py setup` to configure
- Or ensure `config/client_profile.json` exists with valid `client_config.api_token`

### "Authentication failed"
- Check that your API token is valid and not revoked
- Contact server administrator to verify your token
- Ensure your client_id matches what the server expects

### "Rate limit exceeded"
- Your client is sending too many requests
- Wait a minute and try reconnecting
- Contact administrator if this persists

### Connection Issues
- Verify the base URL is correct (domain and protocol)
- Check network connectivity to the server
- Ensure firewall allows outbound connections on the specified port

## Configuration File Format

```json
{
   "client_config": {
      "client_id": "unique-telescope-identifier",
      "base_url": "https://telescopes.dev/",
      "api_token": "your-authentication-token"
   },
   "location": {}
}
```

### Fields:
- **client_config.client_id**: Unique identifier for your telescope client
- **client_config.base_url**: Base server URL used to derive all endpoints
- **client_config.api_token**: Authentication token provided by server administrator
- **location**: Static/slow-changing site location metadata

The client will exit at startup if required values (`client_id`, `base_url`, `api_token`) are missing or empty.

## Security Notes

- **Keep your API token secure** - don't share it or commit it to version control
- **Use a unique client_id** - avoid conflicts with other telescopes
- **Backup your config** - store your API token safely in case you need to reconfigure

---

For server-side setup and token management, see `WEBSOCKET_SECURITY.md` in the main project directory.