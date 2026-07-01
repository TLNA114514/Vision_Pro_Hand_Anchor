#!/usr/bin/env python3
"""Log WebXR hand-frame WebSocket messages as JSONL."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import websockets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_CERT = ROOT / "certs" / "localhost.pem"
DEFAULT_KEY = ROOT / "certs" / "localhost-key.pem"


class JsonlLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.output_path.open("a", encoding="utf-8")
        self.frame_count = 0
        self.message_count = 0
        self.event_count = 0
        self.invalid_count = 0
        self.last_fps_report_time = time.monotonic()
        self.frames_since_fps_report = 0

    def close(self) -> None:
        self.file.close()

    def write_payload(self, payload: Any) -> None:
        record = {
            "server_receive_time_ns": time.time_ns(),
            "payload": payload,
        }
        self.file.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.file.flush()

    def note_valid_payload(self, payload: Any) -> None:
        self.message_count += 1
        if not isinstance(payload, dict):
            return

        payload_type = payload.get("type")
        if payload_type == "webxr_hand_frame":
            self.frame_count += 1
            self.frames_since_fps_report += 1
            now = time.monotonic()
            elapsed = now - self.last_fps_report_time
            if elapsed >= 1.0:
                server_fps = self.frames_since_fps_report / elapsed
                hands = payload.get("hands", [])
                joint_count = sum(
                    len(hand.get("joints", []))
                    for hand in hands
                    if isinstance(hand, dict)
                )
                client_fps = payload.get("client_fps_estimate")
                client_fps_text = f"{client_fps:.1f}" if isinstance(client_fps, (int, float)) else "n/a"
                print(
                    "fps "
                    f"server={server_fps:.1f} "
                    f"client={client_fps_text} "
                    f"frames={self.frame_count} "
                    f"joints={joint_count} "
                    f"inputs={payload.get('input_source_count')} "
                    f"hand_inputs={payload.get('hand_input_source_count')} "
                    f"mode={payload.get('session_mode')}",
                    flush=True,
                )
                self.frames_since_fps_report = 0
                self.last_fps_report_time = now
        elif payload_type == "webxr_session_event":
            self.event_count += 1
            print(f"session event: {payload.get('event')} {payload}", flush=True)

    def note_invalid(self, reason: str) -> None:
        self.invalid_count += 1
        print(f"invalid message #{self.invalid_count}: {reason}", flush=True)


def make_output_path(data_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return data_dir / f"webxr_hand_{stamp}.jsonl"


async def handle_client(websocket: Any, logger: JsonlLogger) -> None:
    remote = websocket.remote_address
    print(f"client connected: {remote}", flush=True)

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                logger.note_invalid("binary messages are not supported")
                continue

            try:
                payload = json.loads(message)
            except json.JSONDecodeError as exc:
                logger.note_invalid(f"invalid JSON: {exc}")
                continue

            if not isinstance(payload, dict):
                logger.note_invalid("payload is not a JSON object")
                continue

            payload_type = payload.get("type")
            if payload_type != "webxr_hand_frame":
                if payload_type == "webxr_hand_metadata":
                    print("received metadata message", flush=True)
                elif payload_type == "webxr_session_event":
                    pass
                else:
                    logger.note_invalid(f"unexpected payload type: {payload_type!r}")

            logger.note_valid_payload(payload)
            logger.write_payload(payload)
    except websockets.ConnectionClosed:
        pass
    finally:
        print(f"client disconnected: {remote}", flush=True)


def make_ssl_context(cert_path: Path, key_path: Path, no_tls: bool) -> ssl.SSLContext | None:
    if no_tls:
        return None

    if not cert_path.exists() or not key_path.exists():
        print("TLS certificate not found; falling back to plain ws://", flush=True)
        print("run: bash scripts/make_self_signed_cert.sh <LAN_IP>", flush=True)
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


async def run_server(
    host: str,
    port: int,
    output_path: Path,
    ssl_context: ssl.SSLContext | None,
) -> None:
    logger = JsonlLogger(output_path)
    stop_event = asyncio.Event()

    def request_stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            pass

    scheme = "wss" if ssl_context else "ws"
    print(f"writing JSONL to: {logger.output_path}", flush=True)
    print(f"listening on {scheme}://{host}:{port}", flush=True)

    try:
        async with websockets.serve(lambda ws: handle_client(ws, logger), host, port, ssl=ssl_context):
            await stop_event.wait()
    finally:
        logger.close()
        print("server stopped", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory for JSONL logs")
    parser.add_argument("--output", type=Path, help="Explicit JSONL output path")
    parser.add_argument("--cert", type=Path, default=DEFAULT_CERT, help="TLS certificate PEM")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY, help="TLS private key PEM")
    parser.add_argument("--no-tls", action="store_true", help="Serve plain ws:// instead of wss://")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or make_output_path(args.data_dir)
    ssl_context = make_ssl_context(args.cert, args.key, args.no_tls)
    asyncio.run(run_server(args.host, args.port, output_path, ssl_context))


if __name__ == "__main__":
    main()
