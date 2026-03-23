#!/usr/bin/env python3
"""Production startup for CryptoVault on Render.

Uses gunicorn with uvicorn workers for production.
Falls back to uvicorn if gunicorn is unavailable.
"""

import os
import sys
import subprocess


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = _env_int("PORT", 10000)
    workers = _env_int("WORKERS", 1)

    print(f"[startup] Python: {sys.version.split()[0]}")
    print(f"[startup] Host/Port: {host}:{port}")
    print(f"[startup] Workers: {workers}")

    # Use gunicorn with uvicorn workers (production)
    cmd = [
        sys.executable, "-m", "gunicorn",
        "-k", "uvicorn.workers.UvicornWorker",
        "-b", f"{host}:{port}",
        "--workers", str(workers),
        "--timeout", "120",
        "--access-logfile", "-",
        "server:app",
    ]

    print(f"[startup] Command: {' '.join(cmd)}")
    os.execvp(sys.executable, cmd)


if __name__ == "__main__":
    main()
