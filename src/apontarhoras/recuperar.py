"""Recuperação de acesso pelo servidor, sem a interface web (ex.: o único responsável esqueceu a senha).

No pacote portátil (na pasta do ApontarHoras.exe), dois cliques em `RecuperarAcesso.bat`, ou:
    ApontarHoras.exe -m apontarhoras.recuperar <login>
Para desenvolver:
    python -m apontarhoras.recuperar <login> [--config ARQUIVO.ini] [--dados PASTA]

Pede a nova senha temporária no console (sem mostrar, com confirmação), desbloqueia, reativa, encerra as sessões e
obriga a troca no próximo acesso. A pasta de dados vem do `ApontarHoras.ini` ao lado do .exe, como no servidor.
Pode rodar com o servidor ligado (o banco aceita uma escrita por vez e a outra espera).
"""

import argparse
import configparser
import getpass
import sys
from collections.abc import Callable
from pathlib import Path

from apontarhoras.domain.errors import AppError
from apontarhoras.main import load_settings
from apontarhoras.services import users_service
from apontarhoras.storage.db import Database

PROG = "ApontarHoras.exe -m apontarhoras.recuperar"


def _default_ini() -> Path:
    """O `ApontarHoras.ini` da pasta do executável (no pacote, a pasta do ApontarHoras.exe)."""
    return Path(sys.executable).with_name("ApontarHoras.ini")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=PROG, description="Recupera o acesso de um usuário pelo servidor.")
    parser.add_argument("login", help="login de quem perdeu o acesso")
    parser.add_argument("--config", type=Path, default=None, help="arquivo .ini (padrão: o da pasta do programa)")
    parser.add_argument("--dados", type=Path, default=None, help="pasta do banco de dados (vale mais que o .ini)")
    return parser.parse_args(argv)


def run(
    argv: list[str] | None = None,
    *,
    read_password: Callable[[str], str] = getpass.getpass,
    out: Callable[[str], None] = print,
) -> int:
    """Devolve o código de saída (0 = deu certo). `read_password` é trocado nos testes (sem console)."""
    args = _parse_args(argv)
    settings_argv = ["--config", str(args.config or _default_ini())]
    if args.dados:
        settings_argv += ["--dados", str(args.dados)]
    try:
        settings, _ = load_settings(settings_argv)
    except (ValueError, configparser.Error) as exc:
        out(f"Configuração inválida: {exc}")
        return 1
    db_path = settings.db_path
    if not db_path.is_file():
        out(f"Banco de dados não encontrado em {db_path}. Confira a opção 'dados' do ApontarHoras.ini.")
        return 1

    out(f"Dados: {db_path}")
    out(f"Recuperar o acesso de '{args.login}': defina uma senha temporária (a pessoa troca no próximo acesso).")
    try:
        password = read_password("Nova senha temporária: ")
        confirmation = read_password("Repita a senha: ")
    except (EOFError, KeyboardInterrupt):
        out("\nCancelado. Nada foi alterado.")
        return 1
    if password != confirmation:
        out("As senhas não conferem. Nada foi alterado.")
        return 1

    database = Database(db_path)
    try:
        database.initialize()
    except (OSError, RuntimeError) as exc:
        out(f"Não foi possível abrir os dados em {db_path}: {exc}")
        return 1
    conn = database.connect()
    try:
        user = users_service.recover_access(conn, args.login, password)
    except AppError as exc:
        out(f"Não foi possível recuperar o acesso: {exc} Nada foi alterado.")
        return 1
    finally:
        conn.close()

    out(f"Pronto: {user.name} ({user.login}) pode entrar com a senha temporária e vai ter que trocá-la.")
    out("Acesso desbloqueado e reativado; as sessões abertas foram encerradas. Registrado na auditoria.")
    if not user.is_admin:
        out(f"Atenção: '{user.login}' é {user.role.label.lower()}, não responsável.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
