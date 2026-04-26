import asyncio
import logging
from typing import Any

from src.server import MessageType, ServerTcp
from src.services.api import API

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


api = API()


async def on_server_message(peer: str, message: dict[str, str]) -> None:
    message_type = message.get("type", "").strip().lower()

    if message_type == MessageType.POSITIONS:
        positions = parse_positions_message(message)
        api.set_positions(positions)
        return

    if message_type == MessageType.COMMAND_RESULT:
        command = message.get("command", "?")
        status = message.get("status", "?")
        details = message.get("message", "")
        desc = message.get("desc", "")
        if desc.strip() != "":
            details = f"{details};desc={desc}" if details.strip() != "" else f"desc={desc}"
        api.set_command_result(command, status, details)
        logger.info("Resultado comando %s (%s) de %s: %s", command, status, peer, details)


async def on_server_disconnected(peer: str) -> None:
    api.clear_positions()
    logger.info("Cliente desconectado (%s). Posicoes locais zeradas.", peer)


def run_tcp_server(server: ServerTcp) -> None:
    try:
        asyncio.run(server.run())
    except Exception:
        logger.exception("Falha no servidor TCP.")


def parse_positions_message(message: dict[str, str]) -> list[dict[str, Any]]:
    payload = message.get("payload", "")
    if payload.strip() != "":
        return parse_positions_payload(payload)

    # Fallback: suporte para formato sem payload agregado
    if "ticket" in message or "symbol" in message or "volume" in message:
        return [map_position_row(message)]

    return []


def parse_positions_payload(payload: str) -> list[dict[str, Any]]:
    normalized_payload = payload.strip()
    if normalized_payload == "":
        return []

    normalized_lower = normalized_payload.lower()
    if normalized_lower in {"no positions", "positions not found"}:
        return []

    positions: list[dict[str, Any]] = []
    for row in normalized_payload.split("|"):
        row = row.strip()
        if row == "":
            continue

        item: dict[str, str] = {}
        for token in row.split(","):
            token = token.strip()
            if token == "" or "=" not in token:
                continue
            key, value = token.split("=", 1)
            item[key.strip()] = value.strip()

        if not item:
            continue

        positions.append(map_position_row(item, default_id=str(len(positions) + 1)))

    return positions


def map_position_row(item: dict[str, str], default_id: str = "1") -> dict[str, Any]:
    side = item.get("side", "").lower()
    return {
        # shape compatível com frontend/src/types/position.ts
        "id": item.get("ticket", default_id),
        "lot": parse_float(item.get("volume")),
        "profit": parse_float(item.get("profit")),
        "type": "BUY" if side == "buy" else "SELL",
        # campos extras úteis para evolução futura do frontend
        "ticket": item.get("ticket", ""),
        "symbol": item.get("symbol", ""),
        "side": side,
        "open_price": parse_float(item.get("open_price")),
        "sl": parse_float(item.get("sl")),
        "tp": parse_float(item.get("tp")),
        "time_msc": parse_int(item.get("time_msc")),
    }


def parse_float(raw: str | None) -> float:
    if raw is None or raw.strip() == "":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def parse_int(raw: str | None) -> int:
    if raw is None or raw.strip() == "":
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0
