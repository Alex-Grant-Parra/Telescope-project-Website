# Telescope Client Setup Guide

This guide explains how to configure and run the telescope client with the new authentication system.

## Quick Setup

### Method 1: Interactive Setup (Recommended)

Run the setup command:
```bash
python websocket_client.py setup
```

This will prompt you to enter:
- **Client ID**: Unique identifier for your telescope (e.g., "pi-001", "telescope-main")
- **Server URI**: WebSocket server address (e.g., "ws://telescopes.dev:4000")
- **API Token**: Authentication token from the server administrator

### Method 2: Manual Configuration

1. Copy the example config file:
   ```bash
   cp client_config_example.json client_config.json
   ```

2. Edit `client_config.json` with your settings:
   ```json
   {
     "client_id": "your-unique-telescope-id",
     "server_uri": "ws://your-server-ip:4000",
     "api_token": "your-api-token-from-server-admin"
   }
   ```

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
python websocket_client.py
```

The client will:
- ✅ Connect to the command WebSocket server
- ✅ Connect to the live view WebSocket server  
- ✅ Authenticate using your API token
- ✅ Start sending camera frames and handling telescope commands

## Troubleshooting

### "No API token configured"
- Run `python websocket_client.py setup` to configure
- Or ensure `client_config.json` exists with valid `api_token`

### "Authentication failed"
- Check that your API token is valid and not revoked
- Contact server administrator to verify your token
- Ensure your client_id matches what the server expects

### "Rate limit exceeded"
- Your client is sending too many requests
- Wait a minute and try reconnecting
- Contact administrator if this persists

### Connection Issues
- Verify the server URI is correct (IP address and port)
- Check network connectivity to the server
- Ensure firewall allows outbound connections on the specified port

## Configuration File Format

```json
{
  "client_id": "unique-telescope-identifier",
  "server_uri": "ws://server-ip:4000",
  "api_token": "your-authentication-token"
}
```

### Fields:
- **client_id**: Unique identifier for your telescope client
- **server_uri**: WebSocket server address (include ws:// prefix)
- **api_token**: Authentication token provided by server administrator

## Security Notes

- **Keep your API token secure** - don't share it or commit it to version control
- **Use a unique client_id** - avoid conflicts with other telescopes
- **Backup your config** - store your API token safely in case you need to reconfigure

---

For server-side setup and token management, see `WEBSOCKET_SECURITY.md` in the main project directory.