#!/usr/bin/env python3
"""Serve the web/ directory over HTTPS for local WebXR testing."""

from __future__ import annotations

import argparse
import http.server
import os
import ssl
from functools import partial
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEB_DIR = ROOT / "web"
DEFAULT_CERT = ROOT / "certs" / "localhost.pem"
DEFAULT_KEY = ROOT / "certs" / "localhost-key.pem"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind")
    parser.add_argument("--port", type=int, default=8443, help="HTTPS port")
    parser.add_argument("--directory", type=Path, default=DEFAULT_WEB_DIR, help="Directory to serve")
    parser.add_argument("--cert", type=Path, default=DEFAULT_CERT, help="TLS certificate PEM")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY, help="TLS private key PEM")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = args.directory.resolve()
    cert_path = args.cert.resolve()
    key_path = args.key.resolve()

    if not directory.exists():
        raise SystemExit(f"web directory not found: {directory}")
    if not cert_path.exists() or not key_path.exists():
        raise SystemExit(
            "certificate files not found. Run:\n"
            "  bash scripts/make_self_signed_cert.sh <LAN_IP>"
        )

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"serving {directory}", flush=True)
    print(f"https://{args.host}:{args.port}", flush=True)
    if args.host == "0.0.0.0":
        print("open https://<LAN_IP>:8443 on Vision Pro", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("HTTPS server stopped", flush=True)


if __name__ == "__main__":
    main()
