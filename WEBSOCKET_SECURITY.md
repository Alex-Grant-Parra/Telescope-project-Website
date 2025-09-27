# Secure WebSocket Setup for External Clients

This guide explains how to securely allow external clients to connect to your telescope WebSocket server.

## Security Features Implemented

✅ **Token-based Authentication**: All WebSocket connections require valid API tokens  
✅ **Rate Limiting**: Prevents DoS attacks with request limits per client  
✅ **IP Logging**: All connections are logged with IP addresses  
✅ **Environment Configuration**: Use `WS_IP` environment variable to control binding  
✅ **Input Validation**: JSON parsing and structure validation  
✅ **Connection Timeouts**: Authentication must complete within 10 seconds  

## Quick Setup

### 1. Generate API Tokens

Run the token management utility:
```bash
python manage_tokens.py
```

Choose option 1 to generate a new token, then enter:
- **Client name**: A description (e.g., "My Telescope Controller")
- **Client type**: 
  - `telescope` - Can control telescope hardware
  - `observer` - Can only observe (view-only access)

**Store the generated token securely!** You won't be able to retrieve it again.

### 2. Configure Network Access

Set the environment variable before running your server:

**Windows (PowerShell):**
```powershell
$env:WS_IP = "0.0.0.0"
python Server.py
```

**Windows (Command Prompt):**
```cmd
set WS_IP=0.0.0.0
python Server.py
```

**Linux/Mac:**
```bash
export WS_IP="0.0.0.0"
python Server.py
```

### 3. Firewall Configuration

**Windows Firewall:**
```powershell
# Allow WebSocket ports through firewall
New-NetFirewallRule -DisplayName "Telescope WS Command" -Direction Inbound -Protocol TCP -LocalPort 4000 -Action Allow
New-NetFirewallRule -DisplayName "Telescope WS LiveView" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

**Linux (UFW):**
```bash
sudo ufw allow 4000/tcp comment "Telescope WS Command"
sudo ufw allow 8000/tcp comment "Telescope WS LiveView" 
```

### 4. Router Port Forwarding

Configure your router to forward ports to your telescope server:
- **Port 4000** (TCP) → Your server's internal IP
- **Port 8000** (TCP) → Your server's internal IP
- **Port 5000** (TCP) → Your server's internal IP (Flask web interface)

## Client Connection Protocol

### Authentication Flow

1. **Connect** to WebSocket server
2. **Send authentication** as first message:
   ```json
   {
     "token": "your-api-token-here",
     "client_id": "unique-client-identifier"
   }
   ```
3. **Server validates** token and responds with connection acceptance/rejection
4. **Normal operation** begins if authenticated

### Example Client Code

```python
import asyncio
import websockets
import json

async def connect_telescope():
    uri = "ws://your-server-ip:4000"
    
    async with websockets.connect(uri) as websocket:
        # Send authentication
        auth_msg = {
            "token": "your-api-token-here",
            "client_id": "my-telescope-client"
        }
        await websocket.send(json.dumps(auth_msg))
        
        # Continue with normal WebSocket communication
        # ...
```

## Security Considerations

### For External Access:

1. **Use Strong Tokens**: Generate tokens with the provided utility (32-byte URL-safe)
2. **Limit Token Distribution**: Only give tokens to trusted users/devices
3. **Monitor Logs**: Check security logs regularly for suspicious activity
4. **Regular Token Rotation**: Periodically revoke and regenerate tokens
5. **Consider VPN**: For highest security, use VPN instead of direct internet access

### Network Security:

- **Router Security**: Ensure your router firmware is up-to-date
- **Change Default Ports**: Consider using non-standard ports (edit `commandPort` and `LiveViewPort`)
- **Network Monitoring**: Monitor for unusual traffic patterns

## Token Management

### List Existing Tokens
```bash
python manage_tokens.py
# Choose option 2
```

### Revoke a Token
```bash
python manage_tokens.py
# Choose option 3, then enter the token to revoke
```

### Manual Token File

Alternatively, edit `api_tokens.json` directly:
```json
{
  "your-secure-token-here": {
    "client_type": "telescope",
    "name": "Main Telescope Controller", 
    "created": "2025-09-27T12:00:00"
  }
}
```

## Troubleshooting

### Common Issues:

**"Authentication failed"**
- Check that your token exists in `api_tokens.json`
- Ensure token is sent as first message
- Verify JSON format is correct

**"Rate limit exceeded"** 
- Client is sending too many requests
- Default limit: 60 requests per minute per IP
- Adjust `REQUEST_LIMIT_PER_MINUTE` if needed

**"Client ID required"**
- Include `client_id` in authentication message
- Use a unique identifier for each client instance

### Security Logs

Check `security/logs/security.log` for authentication attempts and security events.

## Environment Variables

- `WS_IP`: WebSocket binding IP (default: "0.0.0.0")
- Set to "127.0.0.1" for localhost-only access
- Set to "0.0.0.0" for external access
- Set to specific IP for network interface binding

---

**⚠️ Important Security Reminder:**
External access increases security risks. Monitor your system regularly and keep tokens secure. Consider using a VPN for the highest level of security.