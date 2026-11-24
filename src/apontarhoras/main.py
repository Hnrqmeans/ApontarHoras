"""Ponto de entrada: lê a configuração, prepara o banco e sobe o servidor.

No pacote portátil, ApontarHoras.exe abre sem argumentos e lê o `ApontarHoras.ini` da mesma pasta (o Python do
pacote não aceita opções próprias na linha de comando). Para desenvolver:
    python -m apontarhoras [--rede] [--porta 8080] [--dados PASTA] [--sem-navegador] [--config ARQUIVO.ini]
Opção na linha de comando vale mais que o .ini.
"""

import argparse
import configparser
import logging
import socket
import threading
import webbrowser
from pathlib import Path

from apontarhoras import APP_NAME, __version__
from apontarhoras.config import Settings, default_data_dir
from apontarhoras.storage.db import Database
from apontarhoras.web.app import App
from apontarhoras.web.server import AppServer

_YES = {"sim", "s", "yes", "true", "1", "on"}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Apontamento de horas (Lei do Bem).")
    parser.add_argument("--config", type=Path, default=None, help="arquivo .ini de configuração")
    parser.add_argument("--rede", action="store_true", default=None,
                        help="aceita acessos de outros computadores (use no servidor da empresa)")
    parser.add_argument("--porta", type=int, default=None, help="porta (padrão: 8080)")
    parser.add_argument("--dados", type=Path, default=None, help="pasta do banco de dados")
    parser.add_argument("--sem-navegador", action="store_true", default=None, help="não abre o navegador ao iniciar")
    parser.add_argument("--versao", action="version", version=f"{APP_NAME} {__version__}")
    return parser.parse_args(argv)


def _read_ini(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8-sig")
    return dict(parser["servidor"]) if parser.has_section("servidor") else {}


def load_settings(argv: list[str] | None = None) -> tuple[Settings, bool]:
    """Configuração final (padrão ← .ini ← linha de comando) e se deve abrir o navegador."""
    args = _parse_args(argv)
    ini = _read_ini(args.config)
    network = args.rede if args.rede is not None else ini.get("rede", "nao").strip().lower() in _YES
    port_text = ini.get("porta", "").strip()
    port = args.porta or (int(port_text) if port_text else 8080)
    data_text = ini.get("dados", "").strip()
    data_dir = args.dados or (Path(data_text) if data_text else default_data_dir())
    open_browser = not args.sem_navegador and ini.get("abrir_navegador", "sim").strip().lower() in _YES
    # https = sim: o app está atrás de um proxy HTTPS; o cookie de sessão ganha `Secure` (nunca vai por HTTP).
    secure_cookies = ini.get("https", "nao").strip().lower() in _YES
    settings = Settings(
        data_dir=data_dir, host="0.0.0.0" if network else "127.0.0.1", port=port, secure_cookies=secure_cookies
    )
    return settings, open_browser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings, open_browser = load_settings(argv)
    except (ValueError, configparser.Error) as exc:
        print(f"Configuração inválida: {exc}")
        return 1
    database = Database(settings.db_path)
    try:
        database.initialize()
    except (OSError, RuntimeError) as exc:
        print(f"Não foi possível abrir os dados em {settings.db_path}: {exc}")
        return 1
    try:
        server = AppServer((settings.host, settings.port), App(database, secure_cookies=settings.secure_cookies))
    except OSError as exc:
        print(f"Não foi possível usar a porta {settings.port} ({exc}). Ela já está em uso? Troque a porta no .ini.")
        return 1

    local_url = f"http://localhost:{settings.port}/"
    print(f"{APP_NAME} v{__version__} rodando.")
    print(f"  Neste computador: {local_url}")
    if settings.host == "0.0.0.0":
        print(f"  Na rede/VPN:      http://{socket.gethostname()}:{settings.port}/")
    print(f"  Dados:            {settings.db_path}")
    print("  Para parar: feche esta janela (ou Ctrl+C).")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(local_url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
