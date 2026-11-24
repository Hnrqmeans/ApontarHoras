"""Teste de carga do ApontarHoras: vários colaboradores apontando ao mesmo tempo.

Só biblioteca padrão. NÃO roda no pytest normal (o teste leve fica em tests/test_concorrencia.py).

Uso (na pasta do projeto):
    .venv\\Scripts\\python.exe scripts\\carga.py
        sobe o app num banco TEMPORÁRIO (apagado no fim), 20 colaboradores × 20 apontamentos
    .venv\\Scripts\\python.exe scripts\\carga.py --usuarios 50 --apontamentos 10
    .venv\\Scripts\\python.exe scripts\\carga.py --url http://localhost:8090 --admin-login ana --admin-senha ...
        usa um app já rodando (de TESTE: o script cria colaboradores e um projeto "CARGA-..."); com
        --banco <arquivo .db> também confere o que foi gravado
Nunca aponte para o servidor de produção: os cadastros de teste ficam lá (só desativar).

O que faz: cria (ou entra como) o responsável, cria um projeto e N colaboradores; cada colaborador (uma thread)
entra, troca a senha temporária e, todos juntos, lançam M apontamentos (1 h por dia, em dias passados distintos).
Confere: nenhuma resposta 5xx ou falha de conexão, todo apontamento confirmado e, com o banco, total gravado igual
ao esperado e nada duplicado/perdido. Imprime os tempos (médio, p95, máximo).
"""

import argparse
import math
import re
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

TEMP_PASSWORD = "temporaria-carga-1"
USER_PASSWORD = "senha-carga-123"
ADMIN_LOGIN = "carga.admin"
ADMIN_PASSWORD = "senha-carga-admin"
TIMEOUT = 60


@dataclass
class Stats:
    """Tempos (s) por tipo de requisição e falhas. Compartilhado entre as threads (com trava)."""

    times: dict[str, list[float]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, kind: str, seconds: float) -> None:
        with self.lock:
            self.times.setdefault(kind, []).append(seconds)

    def fail(self, message: str) -> None:
        with self.lock:
            self.failures.append(message)


class Client:
    """Navegador mínimo: cookies, campo `csrf` da última página e `Origin` igual à URL base (como um navegador)."""

    def __init__(self, base: str, stats: Stats) -> None:
        self.base = base.rstrip("/")
        self.stats = stats
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.last = ""

    def _open(self, kind: str, request: urllib.request.Request) -> tuple[int, str, str]:
        started = time.perf_counter()
        try:
            with self.opener.open(request, timeout=TIMEOUT) as response:
                status, url, body = response.status, response.url, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            status, url, body = error.code, error.url, error.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as error:
            self.stats.fail(f"{kind}: falha de conexão ({error})")
            return 0, "", ""
        self.stats.add(kind, time.perf_counter() - started)
        if status >= 500:
            self.stats.fail(f"{kind}: HTTP {status}")
        self.last = body
        return status, urllib.parse.urlsplit(url).path, body

    def get(self, path: str, kind: str = "GET") -> tuple[int, str, str]:
        return self._open(kind, urllib.request.Request(self.base + path))

    def post(self, path: str, data: dict[str, str], kind: str = "POST") -> tuple[int, str, str]:
        fields = dict(data)
        match = re.search(r'name="csrf" value="([^"]+)"', self.last)
        if match:
            fields["csrf"] = match.group(1)
        body = urllib.parse.urlencode(fields).encode()
        return self._open(kind, urllib.request.Request(self.base + path, data=body, headers={"Origin": self.base}))


@dataclass
class LoadResult:
    users: int
    entries: int
    stats: Stats
    confirmed: int  # apontamentos com "Apontamento salvo"
    elapsed: float  # segundos da fase de apontamentos
    saved: int | None = None  # contado no banco (None = sem acesso ao banco)
    duplicates: int | None = None
    users_with_wrong_count: int | None = None

    @property
    def expected(self) -> int:
        return self.users * self.entries

    @property
    def ok(self) -> bool:
        db_ok = self.saved is None or (
            self.saved == self.expected and self.duplicates == 0 and self.users_with_wrong_count == 0
        )
        return not self.stats.failures and self.confirmed == self.expected and db_ok


def _login_admin(admin: Client, login: str, password: str) -> None:
    _, path, _ = admin.get("/")
    if path == "/primeiro-acesso":
        _, path, _ = admin.post("/primeiro-acesso", {"nome": "Responsável Carga", "login": login, "senha": password,
                                                     "confirmacao": password})
    elif path == "/entrar":
        _, path, _ = admin.post("/entrar", {"login": login, "senha": password})
    if path != "/":
        raise RuntimeError("Não foi possível entrar como responsável (confira --admin-login/--admin-senha).")


def _prepare(admin: Client, prefix: str, users: int) -> tuple[str, list[str]]:
    code = prefix.upper()
    admin.get("/projetos/novo")
    _, path, _ = admin.post("/projetos/novo", {"codigo": code, "nome": "Projeto do teste de carga", "descricao": "",
                                               "lei_do_bem": "1"})
    if path != "/projetos":
        raise RuntimeError("Não foi possível criar o projeto de teste.")
    logins = []
    for number in range(1, users + 1):
        login = f"{prefix}.{number:03d}"
        admin.get("/usuarios/novo")
        _, path, _ = admin.post("/usuarios/novo", {"nome": f"Colaborador Carga {number:03d}", "login": login,
                                                   "papel": "colaborador", "senha": TEMP_PASSWORD})
        if path != "/usuarios":
            raise RuntimeError(f"Não foi possível criar o colaborador {login}.")
        logins.append(login)
    return code, logins


def _worker(base: str, login: str, code: str, entries: int, stats: Stats, start: threading.Barrier,
            confirmed: list[int]) -> None:
    client = Client(base, stats)
    ready = False
    try:
        client.get("/entrar", "GET /entrar")
        client.post("/entrar", {"login": login, "senha": TEMP_PASSWORD}, "POST /entrar")
        _, path, _ = client.post("/trocar-senha", {"atual": TEMP_PASSWORD, "nova": USER_PASSWORD,
                                                   "confirmacao": USER_PASSWORD}, "POST /trocar-senha")
        _, _, form_page = client.get("/apontamentos/novo", "GET /apontamentos/novo")
        project = re.search(rf'<option value="(\d+)">{re.escape(code)} ', form_page)
        task = re.search(r'<option value="(\d+)">Desenvolvimento', form_page)
        if path != "/" or not project or not task:
            raise RuntimeError("entrar/trocar a senha falhou")
        ready = True
    except Exception as exc:  # registra e segue: o relatório mostra a falha
        stats.fail(f"{login}: {exc}")
    start.wait()
    if not ready:
        return
    today = date.today()
    for number in range(entries):
        day = today - timedelta(days=number)
        client.get("/apontamentos/novo", "GET /apontamentos/novo")
        _, path, body = client.post(
            "/apontamentos/novo",
            {"data": day.isoformat(), "projeto": project.group(1), "tarefa": task.group(1), "inicio": "8",
             "termino": "9", "almoco": "", "descricao": f"Teste de carga {number + 1}"},
            "POST /apontamentos/novo",
        )
        if path == "/apontamentos" and "Apontamento salvo" in body:
            with stats.lock:
                confirmed[0] += 1
        else:
            stats.fail(f"{login}: apontamento de {day.isoformat()} não confirmado")


def _check_database(result: LoadResult, db_path: Path, prefix: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        like = (prefix + ".%",)
        result.saved = conn.execute(
            "SELECT COUNT(*) FROM time_entries t JOIN users u ON u.id = t.user_id WHERE u.login LIKE ?", like
        ).fetchone()[0]
        result.duplicates = conn.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM time_entries t JOIN users u ON u.id = t.user_id WHERE u.login LIKE ?"
            " GROUP BY t.user_id, t.work_date, t.start_minute HAVING COUNT(*) > 1)", like
        ).fetchone()[0]
        per_user = conn.execute(
            "SELECT COUNT(t.id) FROM users u LEFT JOIN time_entries t ON t.user_id = u.id WHERE u.login LIKE ? "
            "GROUP BY u.id", like
        ).fetchall()
        result.users_with_wrong_count = sum(1 for (count,) in per_user if count != result.entries) + max(
            0, result.users - len(per_user)
        )
    finally:
        conn.close()


def run_load(
    base: str,
    *,
    users: int = 20,
    entries: int = 20,
    admin_login: str = ADMIN_LOGIN,
    admin_password: str = ADMIN_PASSWORD,
    db_path: Path | None = None,
) -> LoadResult:
    """Prepara os cadastros, dispara os colaboradores em paralelo e confere o resultado."""
    stats = Stats()
    admin = Client(base, stats)
    _login_admin(admin, admin_login, admin_password)
    prefix = "carga" + secrets.token_hex(3)
    code, logins = _prepare(admin, prefix, users)

    start = threading.Barrier(users + 1)
    confirmed = [0]
    threads = [
        threading.Thread(target=_worker, args=(base, login, code, entries, stats, start, confirmed), daemon=True)
        for login in logins
    ]
    for thread in threads:
        thread.start()
    start.wait()  # todos entraram e trocaram a senha: agora apontam juntos
    began = time.perf_counter()
    for thread in threads:
        thread.join()
    result = LoadResult(users, entries, stats, confirmed[0], time.perf_counter() - began)
    if db_path is not None:
        _check_database(result, db_path, prefix)
    return result


def _summary(values: list[float]) -> str:
    ordered = sorted(values)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    mean = sum(ordered) / len(ordered)
    return (f"{len(ordered):5d} req · médio {mean * 1000:7.1f} ms · p95 {p95 * 1000:7.1f} ms · "
            f"máx {ordered[-1] * 1000:7.1f} ms")


def report(result: LoadResult) -> str:
    lines = [f"Carga: {result.users} colaboradores × {result.entries} apontamentos = {result.expected} esperados"]
    for kind in sorted(result.stats.times):
        lines.append(f"  {kind:26s} {_summary(result.stats.times[kind])}")
    all_times = [t for values in result.stats.times.values() for t in values]
    if all_times:
        lines.append(f"  {'todas':26s} {_summary(all_times)}")
    rate = result.confirmed / result.elapsed if result.elapsed else 0
    lines.append(f"  Fase de apontamentos: {result.elapsed:.1f} s ({rate:.1f} apontamentos/s)")
    lines.append(f"  Confirmados pela tela: {result.confirmed}/{result.expected}")
    if result.saved is None:
        lines.append("  Banco: não conferido (informe --banco para conferir)")
    else:
        lines.append(f"  Banco: {result.saved}/{result.expected} gravados · {result.duplicates} duplicados · "
                     f"{result.users_with_wrong_count} colaboradores com total errado")
    lines.append(f"  Falhas (5xx, conexão, não confirmados): {len(result.stats.failures)}")
    lines.extend(f"    - {failure}" for failure in result.stats.failures[:20])
    lines.append("RESULTADO: OK" if result.ok else "RESULTADO: FALHOU")
    return "\n".join(lines)


def _local_server(folder: Path):
    """Sobe o app numa porta livre com banco novo. Devolve (url, caminho do banco, servidor)."""
    try:
        import apontarhoras  # noqa: F401
    except ImportError:  # rodando direto do repositório, sem instalação
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from apontarhoras.storage.db import Database
    from apontarhoras.web.app import App
    from apontarhoras.web.server import AppServer

    database = Database(folder / "carga.db")
    database.initialize()
    server = AppServer(("127.0.0.1", 0), App(database))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}", database.path, server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teste de carga do ApontarHoras (só para ambiente de teste).")
    parser.add_argument("--usuarios", type=int, default=20, help="colaboradores simultâneos (padrão 20)")
    parser.add_argument("--apontamentos", type=int, default=20, help="apontamentos por colaborador (padrão 20)")
    parser.add_argument("--url", help="app já rodando (ex.: http://localhost:8090); sem isto, sobe um temporário")
    parser.add_argument("--admin-login", default=ADMIN_LOGIN, help="login do responsável (com --url)")
    parser.add_argument("--admin-senha", default=ADMIN_PASSWORD, help="senha do responsável (com --url)")
    parser.add_argument("--banco", type=Path, help="arquivo .db do app em --url, para conferir o que foi gravado")
    args = parser.parse_args(argv)
    if args.usuarios < 1 or args.apontamentos < 1:
        parser.error("--usuarios e --apontamentos precisam ser maiores que zero")

    if args.url:
        result = run_load(args.url, users=args.usuarios, entries=args.apontamentos, admin_login=args.admin_login,
                          admin_password=args.admin_senha, db_path=args.banco)
        print(report(result))
        return 0 if result.ok else 1

    with tempfile.TemporaryDirectory(prefix="apontarhoras-carga-") as folder:
        url, db_path, server = _local_server(Path(folder))
        try:
            result = run_load(url, users=args.usuarios, entries=args.apontamentos, db_path=db_path)
        finally:
            server.shutdown()
            server.server_close()
        print(report(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
