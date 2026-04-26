import asyncio
import concurrent.futures
import inspect
import ipaddress
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 47001
    read_timeout_sec: float = 5.0
    loopback_only: bool = True


class MessageType:
    HELLO = "hello"
    HELLO_ACK = "hello_ack"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    COMMAND_RESULT = "command_result"
    POSITIONS = "positions"
    BUY = "buy"
    SELL = "sell"
    CLOSE_ALL = "close_all"
    CLOSE_POSITION = "close_position"
    PRICE_TICK = "price_tick"  # compatibilidade com payload legado


MessageHandler = Callable[[str, dict[str, str]], Awaitable[None] | None]
DisconnectHandler = Callable[[str], Awaitable[None] | None]


class ServerTcp:
    _instance: Optional["ServerTcp"] = None

    def __new__(cls, config: ServerConfig | None = None) -> "ServerTcp":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: ServerConfig | None = None) -> None:
        if config is None:
            config = ServerConfig()

        if getattr(self, "_initialized", False):
            self.config = config
            return

        self.config = config
        self._server: asyncio.AbstractServer | None = None
        self._message_handler: MessageHandler | None = None
        self._disconnect_handler: DisconnectHandler | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._latest_writer: asyncio.StreamWriter | None = None
        self._writers_lock = threading.Lock()
        self._initialized = True

    @classmethod
    def get_instance(cls, config: ServerConfig | None = None) -> "ServerTcp":
        return cls(config)

    def set_message_handler(self, handler: MessageHandler | None) -> None:
        self._message_handler = handler

    def set_disconnect_handler(self, handler: DisconnectHandler | None) -> None:
        self._disconnect_handler = handler

    async def _notify_message(self, peer: str, message: dict[str, str]) -> None:
        if self._message_handler is None:
            return

        try:
            result = self._message_handler(peer, dict(message))
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            print(f"[tcp] erro no callback de mensagem ({peer}): {exc}")

    async def _notify_disconnected(self, peer: str) -> None:
        if self._disconnect_handler is None:
            return

        try:
            result = self._disconnect_handler(peer)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            print(f"[tcp] erro no callback de desconexao ({peer}): {exc}")

    @staticmethod
    def now_epoch_ms() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def is_loopback_address(address: str) -> bool:
        try:
            return ipaddress.ip_address(address).is_loopback
        except ValueError:
            return False

    @staticmethod
    def parse_key_value_line(raw_line: str) -> dict[str, str]:
        data: dict[str, str] = {}

        for token in raw_line.split(";"):
            token = token.strip()
            if not token:
                continue
            if "=" not in token:
                raise ValueError(f"token invalido: {token!r}")
            key, value = token.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError("chave vazia")
            data[key] = value

        if not data:
            raise ValueError("mensagem vazia")

        return data

    @staticmethod
    def to_line(payload: dict[str, str]) -> str:
        safe_parts = []

        for key, value in payload.items():
            sanitized = value.replace("\n", " ").replace("\r", " ").replace(";", ",")
            safe_parts.append(f"{key}={sanitized}")

        return ";".join(safe_parts) + "\n"

    async def send_message(self, writer: asyncio.StreamWriter, payload: dict[str, str]) -> None:
        writer.write(self.to_line(payload).encode("utf-8"))
        await writer.drain()

    def send_command(self, payload: dict[str, str], timeout_sec: float = 2.0) -> bool:
        loop = self._loop
        writer = self._get_active_writer()
        if loop is None or writer is None:
            return False

        payload_copy = {str(key): str(value) for key, value in payload.items()}

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is loop:
            loop.create_task(self.send_message(writer, payload_copy))
            return True

        future = asyncio.run_coroutine_threadsafe(self.send_message(writer, payload_copy), loop)
        try:
            future.result(timeout=timeout_sec)
            return True
        except (ConnectionResetError, BrokenPipeError, OSError, concurrent.futures.TimeoutError):
            return False

    def _get_active_writer(self) -> asyncio.StreamWriter | None:
        with self._writers_lock:
            if self._latest_writer is not None and not self._latest_writer.is_closing():
                return self._latest_writer

            for writer in self._writers:
                if not writer.is_closing():
                    self._latest_writer = writer
                    return writer

            self._latest_writer = None
            return None

    def _register_writer(self, writer: asyncio.StreamWriter) -> None:
        with self._writers_lock:
            self._writers.add(writer)
            self._latest_writer = writer

    def _unregister_writer(self, writer: asyncio.StreamWriter) -> None:
        with self._writers_lock:
            if writer in self._writers:
                self._writers.remove(writer)

            if self._latest_writer is writer:
                self._latest_writer = next(iter(self._writers), None)

    def _has_connected_clients(self) -> bool:
        with self._writers_lock:
            return len(self._writers) > 0

    async def close_writer_safely(self, writer: asyncio.StreamWriter, peer: str) -> None:
        writer.close()

        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError, OSError):
            print(f"[tcp] fechamento com erro ignorado para {peer}")

    async def handle_message(self, message: dict[str, str], writer: asyncio.StreamWriter, peer: str) -> None:
        raw_type = message.get("type", "")
        message_type = raw_type.strip().lower()

        if not message_type:
            await self.send_message(writer, {"type": MessageType.ERROR, "reason": "missing_type"})
            return

        if message_type == MessageType.HELLO:
            print(f"[tcp] {peer} -> hello ({message})")
            await self.send_message(writer, {"type": MessageType.HELLO_ACK, "server": "python", "protocol": "kv-v1", "ts": str(self.now_epoch_ms())})
            return

        if message_type == MessageType.HEARTBEAT:
            ts = message.get("ts", str(self.now_epoch_ms()))
            await self.send_message(writer, {"type": MessageType.HEARTBEAT_ACK, "ts": ts})
            return

        if message_type == MessageType.HEARTBEAT_ACK:
            print(f"[tcp] {peer} -> heartbeat_ack ({message.get('ts', '-')})")
            return

        if message_type == MessageType.ERROR:
            print(f"[tcp] {peer} -> error ({message})")
            return

        if message_type == MessageType.COMMAND_RESULT:
            command = message.get("command", "?")
            status = message.get("status", "?")
            details = message.get("message", "")
            print(f"[tcp] {peer} -> command_result command={command} status={status} message={details}")
            return

        if message_type == MessageType.POSITIONS:
            return

        if message_type == MessageType.PRICE_TICK:
            symbol = message.get("symbol", "?")
            bid = message.get("bid", "?")
            ask = message.get("ask", "?")
            spread = message.get("spread", "?")
            print(f"[tcp] {peer} -> tick {symbol} bid={bid} ask={ask} spread={spread}")
            return

        print(f"[tcp] {peer} -> tipo nao suportado: {raw_type}")
        await self.send_message(writer, {"type": MessageType.ERROR, "reason": "unsupported_type", "received_type": raw_type})

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peername: tuple | None = writer.get_extra_info("peername")
        peer_ip = str(peername[0]) if peername else "unknown"
        peer_port = str(peername[1]) if peername else "?"
        peer = f"{peer_ip}:{peer_port}"

        if self.config.loopback_only and not self.is_loopback_address(peer_ip):
            print(f"[tcp] conexao recusada (nao-loopback): {peer}")
            await self.close_writer_safely(writer, peer)
            return

        print(f"[tcp] cliente conectado: {peer}")
        self._register_writer(writer)
        try:
            while True:
                try:
                    raw_line = await asyncio.wait_for(reader.readline(), timeout=self.config.read_timeout_sec)
                except TimeoutError:
                    continue

                if not raw_line:
                    print(f"[tcp] cliente desconectou: {peer}")
                    break

                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    parsed = self.parse_key_value_line(line)
                except ValueError as exc:
                    print(f"[tcp] {peer} -> mensagem invalida: {line!r} ({exc})")
                    await self.send_message(writer, {"type": MessageType.ERROR, "reason": "invalid_message"})
                    continue

                await self._notify_message(peer, parsed)
                await self.handle_message(parsed, writer, peer)
        except (ConnectionResetError, BrokenPipeError, OSError):
            print(f"[tcp] conexao resetada pelo cliente: {peer}")
        finally:
            self._unregister_writer(writer)
            if not self._has_connected_clients():
                await self._notify_disconnected(peer)
            await self.close_writer_safely(writer, peer)
            print(f"[tcp] conexao finalizada: {peer}")

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(self.handle_client, host=self.config.host, port=self.config.port)

        sockets = self._server.sockets or []
        if sockets:
            bound = ", ".join(str(sock.getsockname()) for sock in sockets)
            print(f"Servidor TCP pronto em {bound}")

        print("Protocolo: key=value por linha (UTF-8)")
        print(f"Loopback only: {self.config.loopback_only}")
        print("Pressione Ctrl+C para encerrar.")

        async with self._server:
            await self._server.serve_forever()
