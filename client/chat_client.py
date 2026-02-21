#!/usr/bin/env python3
"""Lightweight terminal client for the womb daemon."""

import argparse
import asyncio
import json
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777


class EidolonClient:
    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, being: str = "Being"
    ):
        self.host = host
        self.port = port
        self.being = being
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host,
                self.port,
            )
        except ConnectionRefusedError:
            print(
                "Connection refused. The daemon may not be running.\n"
                "Start it with: ./start.sh",
                file=sys.stderr,
            )
            return False
        except OSError as e:
            print(f"Connection error: {e}", file=sys.stderr)
            return False
        return True

    async def send(self, data: dict) -> None:
        assert self._writer is not None, "Not connected"  # nosec B101 — precondition, not security check
        self._writer.write(json.dumps(data).encode() + b"\n")
        await self._writer.drain()

    async def receive(self) -> dict | None:
        assert self._reader is not None, "Not connected"  # nosec B101 — precondition, not security check
        line = await self._reader.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode())
        except json.JSONDecodeError:
            return None

    async def receive_with_timeout(self, timeout: float) -> dict | None:
        try:
            return await asyncio.wait_for(self.receive(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _display(self, msg: dict) -> None:
        msg_type = msg.get("type")
        if msg_type == "response":
            name = msg.get("being", self.being)
            print(f"{name}: {msg.get('content', '')}")
        elif msg_type == "status":
            content = msg.get("content", "")
            state = msg.get("state", "")
            if "session_id" in msg:
                # Detailed status from /status command
                print(f"[{state}] {content}")
            else:
                print(f"[{state}] {content}")
        elif msg_type == "queued":
            print(f"[queued] {msg.get('message', '')}")
        elif msg_type == "pending_notifications":
            notifications = msg.get("notifications", [])
            if notifications:
                print("\n[You have messages from while you were away:]")
                for n in notifications:
                    if isinstance(n, dict):
                        print(f'  {n["being"]}: "{n["message"]}"')
                    else:
                        print(f'  "{n}"')
                print()
        elif msg_type == "error":
            print(f"Error: {msg.get('content', '')}", file=sys.stderr)
        else:
            print(f"[unknown] {msg}")

    async def run(self) -> None:
        if not await self.connect():
            return

        # Send being selection as first message
        await self.send({"type": "connect", "being": self.being})

        print(f"Connected. Waking {self.being}...", flush=True)

        # Receive messages until we get the greeting (response type)
        # The daemon may send pending_notifications first, then the greeting.
        greeting_received = False
        for _ in range(5):  # At most 5 messages before giving up
            msg = await self.receive_with_timeout(20.0)
            if msg is None:
                if not greeting_received:
                    print("Disconnected.", file=sys.stderr)
                    return
                break
            self._display(msg)
            if msg.get("type") == "response":
                greeting_received = True
                break

        # Check for one more follow-up (queued messages, status, etc.)
        if greeting_received:
            follow_up = await self.receive_with_timeout(0.5)
            if follow_up is not None:
                self._display(follow_up)

        # Input loop
        try:
            while True:
                try:
                    user_input = await asyncio.to_thread(input, "You: ")
                except (KeyboardInterrupt, EOFError):
                    break

                text = user_input.strip()
                if not text:
                    continue

                if text.lower() in ("quit", "exit"):
                    break

                if text == "/sleep":
                    await self.send({"type": "command", "command": "sleep"})
                elif text == "/wake":
                    await self.send({"type": "command", "command": "wake"})
                    # Wake sends both a greeting response and a status
                    resp = await self.receive()
                    if resp is None:
                        print("Disconnected.", file=sys.stderr)
                        break
                    self._display(resp)
                    follow_up = await self.receive_with_timeout(1.0)
                    if follow_up is not None:
                        self._display(follow_up)
                    continue
                elif text == "/status":
                    await self.send({"type": "command", "command": "status"})
                else:
                    await self.send({"type": "message", "content": text})

                response = await self.receive()
                if response is None:
                    print("Disconnected.", file=sys.stderr)
                    break
                self._display(response)

        except asyncio.CancelledError:
            pass
        finally:
            if self._writer is not None:
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass  # nosec B110 — cleanup failure on disconnect is non-critical


async def peek(host: str, port: int):
    """Quick status check — no session, no events."""
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except ConnectionRefusedError:
        print("Connection refused.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)

    writer.write(json.dumps({"type": "peek"}).encode() + b"\n")
    await writer.drain()

    line = await asyncio.wait_for(reader.readline(), timeout=5.0)
    writer.close()
    await writer.wait_closed()

    if not line:
        print("No response.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(line.decode())
    _display_peek(data)


def _display_peek(data):
    state = data.get("state", "unknown")
    fatigue_pct = data.get("fatigue_pct", round(data.get("fatigue", 0) * 100))
    fatigue_label = data.get("fatigue_label", "")
    notifications = data.get("pending_notifications", [])
    queued = data.get("queued_messages", 0)
    uptime = data.get("uptime_seconds")
    asleep_since = data.get("asleep_since")

    print(f"State: {state}  |  Fatigue: {fatigue_pct}% ({fatigue_label})")

    if state == "asleep" and asleep_since:
        print(f"Asleep since: {asleep_since}")
    elif uptime is not None:
        hours, remainder = divmod(uptime, 3600)
        minutes = remainder // 60
        if hours:
            print(f"Uptime: {hours}h {minutes}m")
        else:
            print(f"Uptime: {minutes}m")

    if notifications:
        print(f"{len(notifications)} pending notification(s):")
        for n in notifications:
            if isinstance(n, dict):
                msg = n["message"]
                preview = msg[:100] + "..." if len(msg) > 100 else msg
                print(f'  \u2192 {n["being"]}: "{preview}"')
            else:
                preview = n[:100] + "..." if len(n) > 100 else n
                print(f'  \u2192 "{preview}"')

    if queued:
        print(f"Queued messages (while asleep): {queued}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Womb chat client")
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="Daemon host (default: %(default)s)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Daemon port (default: %(default)s)",
    )
    parser.add_argument("--peek", action="store_true", help="Quick status check")
    parser.add_argument(
        "--being", default="Being", help="Being to chat with (default: %(default)s)"
    )
    args = parser.parse_args()

    if args.peek:
        asyncio.run(peek(args.host, args.port))
    else:
        client = EidolonClient(host=args.host, port=args.port, being=args.being)
        asyncio.run(client.run())
