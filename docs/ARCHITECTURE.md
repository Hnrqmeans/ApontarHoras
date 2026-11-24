# ARCHITECTURE — Estrutura, camadas e integrações

## Decisões técnicas
| Data       | Decisão                                   | Motivo                                                                 |
|------------|-------------------------------------------|------------------------------------------------------------------------|
| 2026-11-23 | **Servidor da empresa** + VPN p/ remotos  | Empresa já tem servidor; uma pessoa exporta os dados de todos sem ninguém enviar arquivo. |
| 2026-11-23 | **Só biblioteca padrão** (zero dependências) | Pedido do usuário: abrir em máquina limpa. Sem NiceGUI/Flask/openpyxl. |
| 2026-11-23 | `http.server` (ThreadingHTTPServer) + HTML gerado no servidor | Interface pelo navegador; nada a instalar nos PCs da equipe. |
| 2026-11-23 | Sem JavaScript; CSP `script-src 'none'`   | Menos superfície de ataque (XSS); páginas simples bastam.              |
| 2026-11-23 | SQLite em modo WAL, 1 conexão por requisição, `BEGIN IMMEDIATE` | Dezenas de usuários sem servidor de banco; escrita concorrente espera em vez de falhar. |
| 2026-11-23 | Senha com `hashlib.scrypt`; sessão = token aleatório, banco guarda só o SHA-256 | Quem ler o arquivo do banco não obtém senhas nem sessões. |
| 2026-11-23 | Duração em minutos (int)                  | Evita erro de arredondamento de horas em `float`.                      |
| 2026-11-23 | Pacote = Python 3.12 embeddable oficial; `python.exe` renomeado `ApontarHoras.exe` | Assinado pela PSF (PyInstaller é bloqueado pelo Windows); console mostra o endereço. |
| 2026-11-23 | Configuração em `ApontarHoras.ini` ao lado do .exe | O Python embutido recusa opções `--` desconhecidas na linha de comando. |

## Como roda
```
 PCs da equipe (navegador)  ──rede/VPN──►  Servidor da empresa: ApontarHoras.exe  ──►  apontarhoras.db (pasta com backup)
                                            (porta do .ini, ex.: 8080)
```
- Dev: `.venv\Scripts\python.exe -m apontarhoras` (abre http://localhost:8080; dados em `%LOCALAPPDATA%\ApontarHoras`).
- Servidor: `ApontarHoras.ini` com `rede = sim`, `abrir_navegador = nao`, `dados = <pasta com backup>`.
- Primeiro acesso (banco vazio): a tela `/primeiro-acesso` cria o responsável. Depois disso, some.

## Camadas (dependência só para baixo)
```
web  ──►  services  ──►  storage
  \          │             │
   └────►  domain  ◄───────┘        auth (senha/token) ◄── services
```
- **domain**: modelos e regras puras (validações, duração, bloqueio por tentativas). Não faz I/O.
- **storage**: SQLite; único lugar com SQL. Migrações numeradas em `storage/migrations/NNN_*.sql` (`PRAGMA user_version`).
- **services**: casos de uso + **checagem de permissão** + auditoria, na mesma transação.
- **auth**: hash de senha (scrypt) e tokens (sessão, anti-CSRF).
- **web**: servidor, rotas e telas. Primeira barreira (login/papel/CSRF/origem) em `web/app.py`; os services
  conferem de novo.

## Mapa de módulos (✅ existe · ⏳ planejado)
```
ApontarHoras/
├── CLAUDE.md, README.md, docs/      ✅
├── pyproject.toml                   ✅ dependencies = [] ; extra dev = pytest + ruff
├── .github/workflows/ci.yml         ✅ lint + testes (Windows) em push/PR para dev e main
├── scripts/
│   ├── build.ps1                    ✅ lint+testes → Python embeddable (SHA-256 + assinatura) → dist\ApontarHoras + zip
│   └── portable/
│       ├── sitecustomize.py         ✅ ApontarHoras.exe sem argumentos → main(["--config", ApontarHoras.ini])
│       └── ApontarHoras.ini         ✅ configuração padrão (rede, porta, dados, abrir_navegador)
├── src/apontarhoras/
│   ├── __init__.py                  ✅ __version__, APP_NAME
│   ├── __main__.py / main.py        ✅ load_settings (padrão ← .ini ← linha de comando), sobe o servidor
│   ├── config.py                    ✅ Settings, pasta de dados padrão (APONTARHORAS_DADOS / %LOCALAPPDATA%)
│   ├── domain/
│   │   ├── errors.py                ✅ AppError → ValidationError, PermissionDenied, NotFound, AuthError
│   │   ├── duration.py              ✅ minutos ⇄ "H:MM"; parse de "8", "8:30", "8h30", "8,5"
│   │   ├── user.py                  ✅ User, Role (admin=Responsável, colaborador), login/senha, bloqueio
│   │   ├── project.py               ✅ Project + validações (código único em maiúsculas)
│   │   ├── audit.py                 ✅ AuditEntry, rótulos, changes() (só o que mudou)
│   │   ├── task.py                  ✅ Task (tipo de atividade, Lei do Bem)
│   │   ├── time_entry.py            ✅ horário (7, 730, 7:30), almoço, duração, sobreposição, data, mês
│   │   ├── workday.py               ✅ jornada seg–qui 8h27 / sex 7h42; OK / Pendência / Verificar
│   │   └── period.py                ⏳ fechamento do mês
│   ├── auth/passwords.py, tokens.py ✅ scrypt; token de sessão; csrf_for
│   ├── storage/
│   │   ├── db.py                    ✅ Database, transaction, migrate, datas UTC ISO
│   │   ├── migrations/001_init.sql  ✅ users, sessions, projects, audit_log
│   │   ├── migrations/002_apontamentos.sql ✅ tasks (+9 padrão), projects.rd_eligible, time_entries
│   │   └── users_repo, sessions_repo, projects_repo, tasks_repo, time_entries_repo, audit_repo ✅
│   ├── services/
│   │   ├── common.py                ✅ utcnow, require_user, require_admin
│   │   ├── auth_service.py          ✅ primeiro acesso, login (bloqueio 5× / 15 min), sessão 12 h, trocar senha
│   │   ├── users_service.py         ✅ CRUD + redefinir senha; sempre ≥ 1 responsável; não se rebaixa/exclui
│   │   ├── projects_service.py      ✅ CRUD; colaborador vê só ativos; com horas: só desativar
│   │   ├── tasks_service.py         ✅ CRUD de tarefas (responsável)
│   │   ├── time_entries_service.py  ✅ apontar/corrigir/excluir (dono ou responsável), resumo do mês
│   │   └── audit.py                 ✅ record (na transação), list_recent (só responsável)
│   └── web/
│       ├── server.py                ✅ AppServer (ThreadingHTTPServer), limite de 1 MB por envio
│       ├── app.py                   ✅ despacho, travas, cabeçalhos de segurança, arquivos estáticos
│       ├── http.py, routing.py      ✅ Request/Response, Route/Access/Ctx
│       ├── components.py            ✅ layout, campos, form (com CSRF), e() (escape), mensagens
│       ├── static/style.css         ✅ tema claro/escuro automático
│       └── pages/                   ✅ auth, home, entries (apontamentos), users, projects, tasks, audit
└── tests/                           ✅ domain, storage, services (permissões), main (.ini), web (ponta a ponta)
```

## Segurança (implementado na fundação)
- Senha: scrypt com sal; mínimo 8 caracteres; bloqueio de 15 min após 5 erros seguidos; mesma mensagem para
  "usuário não existe" e "senha errada" (com o mesmo tempo de resposta).
- Senha temporária (criada/redefinida pelo responsável) obriga a troca no próximo acesso.
- Sessão: cookie `HttpOnly; SameSite=Strict`, 12 h; trocar senha/desativar/redefinir encerra as outras sessões.
- Formulários: token anti-CSRF + recusa de POST com `Origin` de outro site.
- Cabeçalhos: CSP restritiva, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, `Cache-Control: no-store`.
  (Não `no-referrer`: o navegador passaria a mandar `Origin: null` nos formulários e a trava de origem recusaria
  todos — bug encontrado no teste manual de 2026-11-24.)
- Auditoria de login, bloqueio, cadastros e senhas (nunca grava a senha).
- Servidor só na rede interna/VPN. HTTPS: ⏳ se a TI exigir (certificado da empresa; `Settings.secure_cookies`).

## Servidor da empresa (checklist para a TI)
- Sistema do servidor e permissão para o app iniciar sozinho (Agendador de Tarefas "ao iniciar" ou serviço).
- **Uma porta interna** liberada no firewall (ex.: 8080), acessível pela rede e pela VPN; **não** exposta à internet.
- Nome fixo na rede (ex.: `apontarhoras.<dominio-interno>`) ou IP fixo.
- Pasta para o banco + **backup diário** (copiar `apontarhoras.db` com o app parado, ou backup do volume).
- HTTPS interno com certificado da empresa: desejável conforme a política da TI.

## Opções avaliadas em 2026-11-23 (escolhida a A)
| Opção | Resumo | Por que não (B, C) |
|-------|--------|--------------------|
| **A. Servidor na rede da empresa** | Um app em modo servidor; equipe pelo navegador/VPN. | — |
| B. Nuvem | Igual à A, hospedado com HTTPS. | Custo e exigências de segurança; sem necessidade agora. |
| C. Pasta compartilhada | Arquivo por pessoa, responsável consolida. | Sem tempo real; conflitos; SQLite em pasta de rede corrompe. |
