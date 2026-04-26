import argparse
import logging
import sys
import threading

import webview

from src.bootstrap import api, on_server_disconnected, on_server_message, run_tcp_server
from src.config import add_settings_cli_arguments, load_settings
from src.server import ServerConfig, ServerTcp
from src.single_instance import SingleInstance, activate_existing_window

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def configure_stdio() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Panel (pywebview + TCP bridge)")
    add_settings_cli_arguments(parser)
    return parser.parse_args()


def main() -> None:
    configure_stdio()
    configure_logging()

    try:
        args = parse_args()
        settings = load_settings(args)
        dev_mode = settings.frontend.mode == "dev"

        logger.info("Inicializando Backtest Panel (mode=%s)", settings.frontend.mode)

        single_instance = SingleInstance()
        if not single_instance.acquire():
            logger.info("Outra instancia ja esta em execucao. Trazendo a janela para frente.")
            activate_existing_window(settings.window.title)
            return

        server_config = ServerConfig(
            host=settings.tcp.host,
            port=settings.tcp.port,
            read_timeout_sec=settings.tcp.read_timeout_sec,
            loopback_only=settings.tcp.loopback_only,
        )
        server = ServerTcp.get_instance(server_config)
        server.set_message_handler(on_server_message)
        server.set_disconnect_handler(on_server_disconnected)
        api.set_server(server)

        server_thread = threading.Thread(
            target=run_tcp_server,
            args=(server,),
            name="tcp-server-thread",
            daemon=True,
        )
        server_thread.start()

        webview.create_window(
            js_api=api,
            on_top=True,
            resizable=False,
            title=settings.window.title,
            url=settings.frontend.entry_url,
            width=settings.window.width,
            height=settings.window.height,
            min_size=(settings.window.min_width, settings.window.min_height),
        )

        logger.info("Iniciando pywebview (http_server=%s)", not dev_mode)
        webview.start(debug=dev_mode, http_server=not dev_mode)
    except KeyboardInterrupt:
        return
    except FileNotFoundError as exc:
        logger.error("Arquivo obrigatorio nao encontrado: %s", exc)
        raise SystemExit(1) from exc
    except Exception as err:
        logger.exception("Erro ao iniciar a aplicacao.")
        raise SystemExit(1) from err


if __name__ == "__main__":
    main()
