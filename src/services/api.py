from threading import Condition, Lock
from typing import Any

from src.server import MessageType, ServerTcp


class API:
    _instance: "API | None" = None
    _initialized: bool
    _positions: list[dict[str, Any]]
    _lock: Lock
    _server: ServerTcp | None
    _command_condition: Condition
    _command_counters: dict[str, int]
    _last_command_results: dict[str, dict[str, str]]

    def __new__(cls) -> "API":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._positions = []
        self._lock = Lock()
        self._server = None
        self._command_condition = Condition()
        self._command_counters = {}
        self._last_command_results = {}
        self._initialized = True

    def set_server(self, server: ServerTcp) -> None:
        self._server = server

    def buy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._send_trade_command(MessageType.BUY, payload)

    def sell(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._send_trade_command(MessageType.SELL, payload)

    def trade(self, payload: dict[str, Any]) -> dict[str, Any]:
        trade_type = self._resolve_trade_type(payload)
        if trade_type == MessageType.BUY:
            return self.buy(payload)
        if trade_type == MessageType.SELL:
            return self.sell(payload)
        return {"ok": False, "error": "invalid_trade_type", "message": "Tipo de trade invalido"}

    def close_all(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        command_payload: dict[str, str] = {"type": MessageType.CLOSE_ALL}

        if payload is not None:
            symbol = self._to_text(payload.get("symbol"))
            if symbol != "":
                command_payload["symbol"] = symbol

        return self._send_command_payload(command_payload, expected_command=MessageType.CLOSE_ALL)

    def close_position(self, payload: dict[str, Any]) -> dict[str, Any]:
        ticket = self._to_int(payload.get("ticket"))
        symbol = self._to_text(payload.get("symbol"))
        command_payload: dict[str, str] = {"type": MessageType.CLOSE_POSITION}

        if ticket is not None and ticket > 0:
            command_payload["ticket"] = str(ticket)
        elif symbol != "":
            command_payload["symbol"] = symbol
        else:
            return {"ok": False, "error": "missing_ticket_or_symbol", "message": "Informe ticket ou symbol"}

        return self._send_command_payload(command_payload, expected_command=MessageType.CLOSE_POSITION)

    def positions(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._positions)

    def set_positions(self, positions: list[dict[str, Any]]) -> None:
        with self._lock:
            self._positions = list(positions)

    def clear_positions(self) -> None:
        with self._lock:
            self._positions = []

    def set_command_result(self, command: str, status: str, message: str) -> None:
        normalized_command = command.strip().lower()
        if normalized_command == "":
            return

        with self._command_condition:
            self._last_command_results[normalized_command] = {
                "command": normalized_command,
                "status": status.strip().lower(),
                "message": message.strip(),
            }
            current = self._command_counters.get(normalized_command, 0)
            self._command_counters[normalized_command] = current + 1
            self._command_condition.notify_all()

    def _send_trade_command(self, command_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._server is None:
            return {"ok": False, "error": "tcp_server_not_configured", "message": "Servidor TCP nao configurado"}

        volume = self._to_float(payload.get("volume"))
        if volume is None or volume <= 0:
            return {"ok": False, "error": "invalid_volume", "message": "Volume invalido"}

        symbol = self._to_text(payload.get("symbol"))
        command_payload: dict[str, str] = {
            "type": command_type,
            "volume": self._format_number(volume),
        }
        if symbol != "":
            command_payload["symbol"] = symbol

        sl = self._to_float(payload.get("sl"))
        if sl is not None:
            command_payload["sl"] = self._format_number(sl)

        tp = self._to_float(payload.get("tp"))
        if tp is not None:
            command_payload["tp"] = self._format_number(tp)

        comment = self._to_text(payload.get("comment"))
        if comment != "":
            command_payload["comment"] = comment

        deviation = self._to_int(payload.get("deviation"))
        if deviation is not None and deviation >= 0:
            command_payload["deviation"] = str(deviation)

        return self._send_command_payload(command_payload, expected_command=command_type)

    def _send_command_payload(self, command_payload: dict[str, str], expected_command: str | None = None) -> dict[str, Any]:
        if self._server is None:
            return {"ok": False, "error": "tcp_server_not_configured", "message": "Servidor TCP nao configurado"}

        start_counter = self._command_counter(expected_command)
        sent = self._server.send_command(command_payload)
        if not sent:
            return {"ok": False, "error": "tcp_client_not_connected", "message": "Cliente TCP nao conectado"}

        if expected_command is not None:
            result = self._wait_for_command_result(expected_command, start_counter, timeout_sec=5.0)
            if result is None:
                return {
                    "ok": False,
                    "error": "command_result_timeout",
                    "message": "Sem resposta do MT5 para o comando",
                }

            status = result.get("status", "")
            details = result.get("message", "")
            if status in {"ok", "partial"}:
                return {"ok": True, "message": details if details != "" else "Command executed"}

            return {"ok": False, "error": "command_failed", "message": details if details != "" else "Command failed"}

        return {"ok": True, "message": "Command sent"}

    def _command_counter(self, command: str | None) -> int:
        if command is None:
            return 0
        normalized = command.strip().lower()
        if normalized == "":
            return 0
        with self._command_condition:
            return self._command_counters.get(normalized, 0)

    def _wait_for_command_result(self, command: str, start_counter: int, timeout_sec: float) -> dict[str, str] | None:
        normalized = command.strip().lower()
        if normalized == "":
            return None

        with self._command_condition:
            current_counter = self._command_counters.get(normalized, 0)
            if current_counter > start_counter:
                return self._last_command_results.get(normalized)

            notified = self._command_condition.wait_for(
                lambda: self._command_counters.get(normalized, 0) > start_counter,
                timeout=timeout_sec,
            )
            if not notified:
                return None

            return self._last_command_results.get(normalized)

    @staticmethod
    def _resolve_trade_type(payload: dict[str, Any]) -> str:
        for key in ("type", "side", "action"):
            raw = payload.get(key)
            if raw is None:
                continue
            value = str(raw).strip().lower()
            if value in {MessageType.BUY, MessageType.SELL}:
                return value
        return ""

    @staticmethod
    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if raw == "":
                return None
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            raw = value.strip()
            if raw == "":
                return None
            try:
                return int(raw)
            except ValueError:
                try:
                    return int(float(raw))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _format_number(value: float) -> str:
        text = f"{value:.8f}".rstrip("0").rstrip(".")
        return text if text != "" else "0"
