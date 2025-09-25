# Main client entry point

import asyncio
from websocket_client import main, cleanup_camera

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()
