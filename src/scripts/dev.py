import atexit
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import psutil
from watchfiles import watch

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
NODE_MODULES_DIR = FRONTEND_DIR / "node_modules"
PNPM_LOCK_FILE = FRONTEND_DIR / "pnpm-lock.yaml"
VITE_URL = "http://localhost:5173"
WATCH_PATHS = [ROOT_DIR / "src"]

_vite_proc: subprocess.Popen | None = None
_app_proc: subprocess.Popen | None = None
_cleanup_done = False
_health_check_thread: threading.Thread | None = None
_stop_health_check = threading.Event()

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def _resolve_cmd(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _resolve_pnpm_cmd() -> list[str]:
    pnpm = _resolve_cmd("pnpm.cmd", "pnpm.exe", "pnpm")
    if pnpm:
        return [pnpm]

    corepack = _resolve_cmd("corepack.cmd", "corepack.exe", "corepack")
    if corepack:
        return [corepack, "pnpm"]

    return []


def resolve_install_cmd() -> list[str]:
    pnpm_cmd = _resolve_pnpm_cmd()
    if pnpm_cmd:
        return [*pnpm_cmd, "install"]

    if PNPM_LOCK_FILE.exists():
        raise FileNotFoundError("Projeto frontend usa pnpm-lock.yaml, mas pnpm/corepack nao foram encontrados no PATH.")

    raise FileNotFoundError("Nao foi possivel encontrar pnpm ou corepack no PATH.")


def resolve_dev_cmd() -> list[str]:
    pnpm_cmd = _resolve_pnpm_cmd()
    if pnpm_cmd:
        return [*pnpm_cmd, "dev"]

    if PNPM_LOCK_FILE.exists():
        raise FileNotFoundError("Projeto frontend usa pnpm-lock.yaml, mas pnpm/corepack nao foram encontrados no PATH.")

    raise FileNotFoundError("Nao foi possivel encontrar pnpm ou corepack no PATH.")


def ensure_frontend_deps() -> None:
    if not FRONTEND_DIR.exists():
        raise FileNotFoundError(f"Diretorio frontend nao encontrado: {FRONTEND_DIR}")

    if NODE_MODULES_DIR.exists():
        return

    cmd = resolve_install_cmd()
    logger.info("Instalando dependencias do frontend...")
    subprocess.run(cmd, cwd=FRONTEND_DIR, check=True, shell=False)


def vite_is_up(url: str) -> bool:
    try:
        with urlopen(url, timeout=2.0) as resp:
            return 200 <= resp.status < 500
    except (URLError, TimeoutError, OSError):
        return False


def wait_for_vite(url: str, max_wait_sec: float = 30.0) -> None:
    logger.info("Aguardando Vite ficar pronto em %s...", url)
    start = time.time()
    while time.time() - start < max_wait_sec:
        if vite_is_up(url):
            logger.info("Vite pronto.")
            return
        time.sleep(0.5)
    raise RuntimeError(f"Vite nao respondeu em {max_wait_sec:.1f}s ({url})")


def health_check_worker(url: str, check_interval: float = 3.0) -> None:
    consecutive_failures = 0
    max_failures = 3

    while not _stop_health_check.is_set():
        if vite_is_up(url):
            if consecutive_failures > 0:
                logger.info("Vite recuperou.")
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                logger.warning("Vite aparenta estar indisponivel (%d falhas seguidas).", consecutive_failures)

        _stop_health_check.wait(check_interval)


def start_vite() -> subprocess.Popen:
    cmd = resolve_dev_cmd()
    logger.info("Iniciando Vite")
    return subprocess.Popen(cmd, cwd=FRONTEND_DIR, shell=False, stdin=subprocess.DEVNULL, stdout=None, stderr=None, creationflags=0)


def kill_tree(proc: subprocess.Popen, timeout: float = 5.0) -> None:
    if proc.poll() is not None:
        return

    try:
        parent = psutil.Process(proc.pid)
    except psutil.Error:
        return

    try:
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []

    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass

    try:
        parent.terminate()
    except psutil.Error:
        pass

    _, alive = psutil.wait_procs([*children, parent], timeout=timeout)

    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            pass

    try:
        psutil.wait_procs(alive, timeout=2.0)
    except psutil.Error:
        pass


def cleanup_on_exit() -> None:
    global _vite_proc, _app_proc, _cleanup_done

    if _cleanup_done:
        return
    _cleanup_done = True

    if _health_check_thread and _health_check_thread.is_alive():
        _stop_health_check.set()
        _health_check_thread.join(timeout=2.0)

    if _app_proc:
        logger.info("Encerrando app Python...")
        kill_tree(_app_proc)
        _app_proc = None

    if _vite_proc:
        logger.info("Encerrando Vite...")
        kill_tree(_vite_proc)
        _vite_proc = None


atexit.register(cleanup_on_exit)


def start_python_app() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [sys.executable, "-m", "src.main", "--mode", "dev"]
    logger.info("Iniciando app Python")
    return subprocess.Popen(cmd, cwd=ROOT_DIR, env=env, shell=False, stdin=subprocess.DEVNULL, stdout=None, stderr=None, creationflags=0)


def restart_python_app() -> None:
    global _app_proc

    if _app_proc and _app_proc.poll() is None:
        logger.info("Reiniciando app Python...")
        kill_tree(_app_proc)

    _app_proc = start_python_app()


def python_hot_reload_loop() -> None:
    restart_python_app()

    existing_paths = [path for path in WATCH_PATHS if path.exists()]
    if not existing_paths:
        raise FileNotFoundError("Nenhum diretorio de watch encontrado (esperado: src/).")

    for changes in watch(*existing_paths):
        has_python_change = any(str(path).endswith(".py") for _, path in changes)
        if not has_python_change:
            continue

        time.sleep(0.15)
        restart_python_app()


def dev() -> None:
    global _vite_proc, _health_check_thread

    configure_logging()
    logger.info("Modo desenvolvimento iniciado")

    try:
        ensure_frontend_deps()
        _vite_proc = start_vite()
        wait_for_vite(VITE_URL)

        _health_check_thread = threading.Thread(
            target=health_check_worker,
            args=(VITE_URL,),
            daemon=True,
            name="vite-health-check",
        )
        _health_check_thread.start()

        python_hot_reload_loop()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuario.")
    except Exception as err:
        if "corepack" in str(err).lower() or "pnpm" in str(err).lower():
            logger.error("Dependencia de frontend indisponivel. Instale/ative pnpm (ex.: `corepack enable pnpm`) e confirme acesso ao registry npm.")
        logger.exception("Falha no runner de desenvolvimento.")
        raise SystemExit(1) from err
    finally:
        cleanup_on_exit()
        logger.info("Dev runner encerrado.")


if __name__ == "__main__":
    dev()
