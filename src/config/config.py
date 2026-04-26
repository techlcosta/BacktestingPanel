import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

VERSION = "0.1.1"

ENV_PREFIX = "FX_BACKTEST_PANEL"
ENV_MODE_KEY = f"{ENV_PREFIX}_MODE"
ENV_DEV_MODE_KEY = f"{ENV_PREFIX}_DEV_MODE"
ENV_LEGACY_DEV_MODE_KEY = ENV_PREFIX
ENV_VITE_PORT_KEY = f"{ENV_PREFIX}_VITE_PORT"
ENV_DEV_URL_KEY = f"{ENV_PREFIX}_DEV_URL"
ENV_DIST_INDEX_KEY = f"{ENV_PREFIX}_DIST_INDEX"

ENV_TCP_HOST_KEY = f"{ENV_PREFIX}_TCP_HOST"
ENV_TCP_PORT_KEY = f"{ENV_PREFIX}_TCP_PORT"
ENV_TCP_READ_TIMEOUT_KEY = f"{ENV_PREFIX}_TCP_READ_TIMEOUT"
ENV_TCP_ALLOW_NON_LOOPBACK_KEY = f"{ENV_PREFIX}_TCP_ALLOW_NON_LOOPBACK"

ENV_WINDOW_TITLE_KEY = f"{ENV_PREFIX}_WINDOW_TITLE"
ENV_WINDOW_WIDTH_KEY = f"{ENV_PREFIX}_WINDOW_WIDTH"
ENV_WINDOW_HEIGHT_KEY = f"{ENV_PREFIX}_WINDOW_HEIGHT"
ENV_WINDOW_MIN_WIDTH_KEY = f"{ENV_PREFIX}_WINDOW_MIN_WIDTH"
ENV_WINDOW_MIN_HEIGHT_KEY = f"{ENV_PREFIX}_WINDOW_MIN_HEIGHT"

DEFAULT_WINDOW_TITLE = "Backtest Panel"
DEFAULT_WINDOW_WIDTH = 520
DEFAULT_WINDOW_HEIGHT = 680
DEFAULT_WINDOW_MIN_WIDTH = 520
DEFAULT_WINDOW_MIN_HEIGHT = 680

DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 47001
DEFAULT_TCP_READ_TIMEOUT = 5.0

DEFAULT_VITE_DEV_PORT = 5173
DEFAULT_FRONTEND_MODE: Literal["dev", "prod"] = "prod"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
CliScalar: TypeAlias = str | int | float | bool


@dataclass(frozen=True, slots=True)
class WindowSettings:
    title: str
    width: int
    height: int
    min_width: int
    min_height: int


@dataclass(frozen=True, slots=True)
class FrontendSettings:
    mode: Literal["dev", "prod"]
    dev_url: str
    dist_index_path: Path
    entry_url: str


@dataclass(frozen=True, slots=True)
class TcpSettings:
    host: str
    port: int
    read_timeout_sec: float
    loopback_only: bool


@dataclass(frozen=True, slots=True)
class AppSettings:
    version: str
    window: WindowSettings
    frontend: FrontendSettings
    tcp: TcpSettings


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_assets_path() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return get_project_root()


def get_frontend_dist_index_path() -> Path:
    if is_frozen():
        return get_assets_path() / "frontend" / "dist" / "index.html"
    return get_project_root() / "frontend" / "dist" / "index.html"


def add_settings_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["dev", "prod"], default=None, help="Modo frontend")
    parser.add_argument("--dev-mode", action="store_true", default=None, help="Atalho para mode=dev")
    parser.add_argument("--dev-url", default=None, help="URL do frontend em dev")
    parser.add_argument("--vite-port", type=int, default=None, help="Porta do Vite")

    parser.add_argument("--host", default=None, help="Host TCP")
    parser.add_argument("--port", type=int, default=None, help="Porta TCP")
    parser.add_argument("--read-timeout", type=float, default=None, help="Timeout TCP")
    parser.add_argument("--allow-non-loopback", action="store_true", default=None, help="Permite clientes fora de loopback")

    parser.add_argument("--window-title", default=None, help="Titulo da janela")
    parser.add_argument("--window-width", type=int, default=None, help="Largura da janela")
    parser.add_argument("--window-height", type=int, default=None, help="Altura da janela")
    parser.add_argument("--window-min-width", type=int, default=None, help="Largura minima")
    parser.add_argument("--window-min-height", type=int, default=None, help="Altura minima")


def resolve_frontend_mode(cli_args: argparse.Namespace | None = None) -> Literal["dev", "prod"]:
    mode: Literal["dev", "prod"] = DEFAULT_FRONTEND_MODE

    env_mode = _read_env(ENV_MODE_KEY)
    env_dev_mode = _read_env_bool(ENV_DEV_MODE_KEY)
    env_legacy_mode = _read_env_bool(ENV_LEGACY_DEV_MODE_KEY)

    if env_mode:
        mode = _parse_mode(env_mode)
    elif env_dev_mode is not None:
        mode = "dev" if env_dev_mode else "prod"
    elif env_legacy_mode is not None:
        mode = "dev" if env_legacy_mode else "prod"

    cli_mode = _get_cli(cli_args, "mode")
    cli_dev_mode = _get_cli(cli_args, "dev_mode")
    if cli_mode:
        mode = _parse_mode(str(cli_mode))
    if cli_dev_mode:
        mode = "dev"

    return mode


def load_settings(cli_args: argparse.Namespace | None = None) -> AppSettings:
    mode = resolve_frontend_mode(cli_args)
    vite_port = _pick_int(cli_args, "vite_port", ENV_VITE_PORT_KEY, DEFAULT_VITE_DEV_PORT)
    dev_url = _pick_str(cli_args, "dev_url", ENV_DEV_URL_KEY, f"http://localhost:{vite_port}")

    dist_index_path = Path(_pick_str(cli_args, None, ENV_DIST_INDEX_KEY, str(get_frontend_dist_index_path()))).resolve()

    if mode == "dev":
        entry_url = dev_url
    else:
        if not dist_index_path.exists():
            raise FileNotFoundError(f"Frontend build nao encontrado em: {dist_index_path}. Build o frontend antes de iniciar em modo prod.")
        entry_url = dist_index_path.as_uri()

    window = WindowSettings(
        title=_pick_str(cli_args, "window_title", ENV_WINDOW_TITLE_KEY, DEFAULT_WINDOW_TITLE),
        width=_pick_int(cli_args, "window_width", ENV_WINDOW_WIDTH_KEY, DEFAULT_WINDOW_WIDTH),
        height=_pick_int(cli_args, "window_height", ENV_WINDOW_HEIGHT_KEY, DEFAULT_WINDOW_HEIGHT),
        min_width=_pick_int(cli_args, "window_min_width", ENV_WINDOW_MIN_WIDTH_KEY, DEFAULT_WINDOW_MIN_WIDTH),
        min_height=_pick_int(cli_args, "window_min_height", ENV_WINDOW_MIN_HEIGHT_KEY, DEFAULT_WINDOW_MIN_HEIGHT),
    )
    _validate_window(window)

    allow_non_loopback = _pick_bool(cli_args, "allow_non_loopback", ENV_TCP_ALLOW_NON_LOOPBACK_KEY, False)
    tcp = TcpSettings(
        host=_pick_str(cli_args, "host", ENV_TCP_HOST_KEY, DEFAULT_TCP_HOST),
        port=_pick_int(cli_args, "port", ENV_TCP_PORT_KEY, DEFAULT_TCP_PORT),
        read_timeout_sec=_pick_float(cli_args, "read_timeout", ENV_TCP_READ_TIMEOUT_KEY, DEFAULT_TCP_READ_TIMEOUT),
        loopback_only=not allow_non_loopback,
    )
    _validate_tcp(tcp)

    return AppSettings(
        version=VERSION,
        window=window,
        frontend=FrontendSettings(mode=mode, dev_url=dev_url, dist_index_path=dist_index_path, entry_url=entry_url),
        tcp=tcp,
    )


def get_config_summary(cli_args: argparse.Namespace | None = None) -> dict[str, object]:
    settings = load_settings(cli_args)
    return {
        "app_version": settings.version,
        "is_frozen": is_frozen(),
        "frontend": {
            "mode": settings.frontend.mode,
            "dev_url": settings.frontend.dev_url,
            "dist_index_path": str(settings.frontend.dist_index_path),
            "dist_exists": settings.frontend.dist_index_path.exists(),
            "entry_url": settings.frontend.entry_url,
        },
        "window": {
            "title": settings.window.title,
            "width": settings.window.width,
            "height": settings.window.height,
            "min_width": settings.window.min_width,
            "min_height": settings.window.min_height,
        },
        "tcp": {
            "host": settings.tcp.host,
            "port": settings.tcp.port,
            "read_timeout_sec": settings.tcp.read_timeout_sec,
            "loopback_only": settings.tcp.loopback_only,
        },
    }


def _get_cli(cli_args: argparse.Namespace | None, name: str) -> CliScalar | None:
    if cli_args is None or not hasattr(cli_args, name):
        return None

    value = getattr(cli_args, name)
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value

    raise TypeError(f"valor de CLI nao suportado para {name}: {type(value).__name__}")


def _read_env(key: str) -> str | None:
    raw = os.environ.get(key)
    if raw is None:
        return None
    value = raw.strip()
    return value if value else None


def _read_env_bool(key: str) -> bool | None:
    raw = _read_env(key)
    if raw is None:
        return None
    return _parse_bool(raw)


def _pick_str(cli_args: argparse.Namespace | None, cli_name: str | None, env_key: str, default: str) -> str:
    if cli_name:
        cli_value = _get_cli(cli_args, cli_name)
        if cli_value is not None:
            value = str(cli_value).strip()
            if value:
                return value
            raise ValueError(f"valor invalido em --{cli_name.replace('_', '-')}: vazio")

    env_value = _read_env(env_key)
    if env_value is not None:
        return env_value

    return default


def _pick_int(cli_args: argparse.Namespace | None, cli_name: str, env_key: str, default: int) -> int:
    cli_value = _get_cli(cli_args, cli_name)
    if cli_value is not None:
        return int(cli_value)

    env_value = _read_env(env_key)
    if env_value is not None:
        return int(env_value)

    return default


def _pick_float(cli_args: argparse.Namespace | None, cli_name: str, env_key: str, default: float) -> float:
    cli_value = _get_cli(cli_args, cli_name)
    if cli_value is not None:
        return float(cli_value)

    env_value = _read_env(env_key)
    if env_value is not None:
        return float(env_value)

    return default


def _pick_bool(cli_args: argparse.Namespace | None, cli_name: str, env_key: str, default: bool) -> bool:
    cli_value = _get_cli(cli_args, cli_name)
    if cli_value is not None:
        return bool(cli_value)

    env_value = _read_env(env_key)
    if env_value is not None:
        return _parse_bool(env_value)

    return default


def _parse_mode(raw: str) -> Literal["dev", "prod"]:
    mode = raw.strip().lower()
    if mode == "dev":
        return "dev"
    if mode == "prod":
        return "prod"
    raise ValueError(f"modo invalido: {raw!r}. Use 'dev' ou 'prod'.")


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"booleano invalido: {raw!r}")


def _validate_window(window: WindowSettings) -> None:
    if window.width <= 0 or window.height <= 0:
        raise ValueError("window width/height devem ser maiores que zero")
    if window.min_width <= 0 or window.min_height <= 0:
        raise ValueError("window min_width/min_height devem ser maiores que zero")
    if window.width < window.min_width or window.height < window.min_height:
        raise ValueError("window width/height nao podem ser menores que min_width/min_height")


def _validate_tcp(tcp: TcpSettings) -> None:
    if not tcp.host.strip():
        raise ValueError("tcp host nao pode ser vazio")
    if tcp.port < 1 or tcp.port > 65535:
        raise ValueError("tcp port deve estar entre 1 e 65535")
    if tcp.read_timeout_sec <= 0:
        raise ValueError("tcp read_timeout_sec deve ser maior que zero")
