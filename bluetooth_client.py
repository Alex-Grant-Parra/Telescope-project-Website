import asyncio

async def bluetoothClient():
    """Placeholder Bluetooth client.

    This module provides a minimal async entrypoint so `Client.py` can import
    `bluetoothClient`. Replace this implementation with the real Bluetooth
    connection logic when available.
    """
    print("[bluetooth] Bluetooth client is not implemented in this repository.")
    print("[bluetooth] Set connectionType to 'websocket' in client_config.json or implement bluetooth_client.py.")
    # Pause briefly so the message is visible when run interactively
    await asyncio.sleep(0.1)
