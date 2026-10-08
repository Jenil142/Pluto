import os
import socket

os.environ["LOG_LEVEL"] = "ERROR"
os.environ["COGNEE_LOG_LEVEL"] = "ERROR"

# Monkey-patch socket to prefer IPv4 over IPv6. 
# This prevents httpx/urllib from hanging for 60s+ on systems where IPv6 is configured but broken/dropped by the ISP.
_orig_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return sorted(res, key=lambda x: x[0] == socket.AF_INET, reverse=True)
socket.getaddrinfo = patched_getaddrinfo

import asyncio
from pluto.core import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting Pluto...")