# ARCHITECTURE — Estrutura, camadas e integrações

## Decisões técnicas
| Data       | Decisão                         | Motivo                                                                  |
|------------|---------------------------------|-------------------------------------------------------------------------|
| 2026-11-23 | Python 3.12 + NiceGUI (proposta)| Mesma stack do Pagodinho: UI só em Python, roda como janela **ou** servidor web. |
| 2026-11-23 | Duração em minutos (int)        | Evita erro de arredondamento de horas em `float`.                       |
| 2026-11-23 | Pacote Python embeddable (proposta) | Técnica já validada no Pagodinho (PyInstaller é bloqueado pelo Windows). |
| 2026-11-23 | **Servidor da empresa (opção A)** + VPN para remotos | A empresa já tem servidor; uma pessoa exporta os dados de todos sem ninguém enviar arquivo. |

## Servidor da empresa (checklist para a TI)
- Sistema do servidor (Windows Server? Linux?) e permissão para rodar o app como **serviço** (sobe sozinho no boot).
- **Uma porta interna** liberada no firewall (ex.: 8080), acessível pela rede e pela VPN; **não** exposta à internet.
- Nome fixo na rede (ex.: `apontarhoras.<dominio-interno>`) ou IP fixo.
- Pasta para o banco + **backup diário** (rotina da TI ou do próprio app).
- HTTPS interno com certificado da empresa: desejável (a VPN já cifra o acesso remoto; na rede local, depende da
  política da TI).
- Requisitos: leves — Python embarcado no pacote, banco SQLite (arquivo único; dezenas de usuários sem problema).

## Opções de arquitetura (avaliadas em 2026-11-23 — escolhida a A)
O ponto central do app é que **vários usuários** gravam e um admin enxerga tudo. Isso muda a arquitetura em relação
ao Pagodinho (um usuário, SQLite local).

| Opção | Como funciona | Prós | Contras |
|-------|---------------|------|---------|
| **A. Servidor na rede da empresa** (recomendada se houver um PC/servidor sempre ligado) | Um único app NiceGUI roda em modo servidor num PC da empresa, com banco (SQLite no início, PostgreSQL se crescer). Cada pessoa abre o **executável** (janela que aponta para o servidor) ou o navegador. | Tempo real; uma base só; atualizar = trocar só o servidor; permissões de verdade. | Precisa de uma máquina ligada e de liberar porta na rede (TI). |
| **B. Nuvem** | Igual à A, mas o servidor fica hospedado (VPS/Azure) com HTTPS. | Funciona fora da empresa/home office. | Custo mensal; segurança/LGPD mais exigentes; domínio e certificado. |
| **C. Pasta compartilhada** | Cada pessoa tem um app local que grava/exporta um arquivo seu numa pasta de rede/OneDrive; o app do admin lê e consolida. | Sem servidor; instalação simples. | Sem tempo real; conflitos de sincronização; permissão depende da pasta; **SQLite em pasta de rede corrompe** se vários escreverem no mesmo arquivo. |

Recomendação: **A**, desenhada de forma que virar **B** seja só mudar onde o servidor roda (o código é o mesmo).
O executável do colaborador vira um "cliente fino": janela nativa (pywebview) apontando para o endereço do servidor,
com o endereço configurável.

## Camadas (dependência só para baixo)
```
ui  ──►  services  ──►  storage
  \          │             │
   └────►  domain  ◄───────┘        integrations ──► services / domain
```
- **domain**: modelos e regras puras (apontamento, período, totais, estados). Não faz I/O.
- **storage**: repositórios; único lugar com SQL. Migrações numeradas.
- **services**: casos de uso + **checagem de permissão** + auditoria, em transação.
- **reports**: consultas agregadas e dados para gráficos/exportação.
- **ui**: telas NiceGUI; só chama services/reports. Esconder botão não é segurança.
- **auth**: login, sessão, hash de senha.
- **integrations**: Excel, e-mail, AD/SSO, ERP — plugáveis.

## Mapa de módulos (✅ existe · ⏳ planejado — atualizar conforme for criado)
```
ApontarHoras/
├── CLAUDE.md                 ✅ guia de início de rotina da IA
├── README.md                 ✅
├── docs/                     ✅ ROADMAP, DEVLOG, ARCHITECTURE, DOMAIN, DESENVOLVEDOR
├── pyproject.toml            ⏳
├── scripts/build.ps1         ⏳ pacote do cliente e do servidor
├── src/apontarhoras/
│   ├── main.py               ⏳ ponto de entrada (modo servidor / modo cliente)
│   ├── config.py             ⏳ endereço do servidor, caminho do banco, porta
│   ├── domain/
│   │   ├── duration.py       ⏳ minutos ⇄ "HH:MM", parse de entrada
│   │   ├── user.py           ⏳ User, Role, permissões (can_*)
│   │   ├── project.py        ⏳ Client, Project, Activity
│   │   ├── time_entry.py     ⏳ TimeEntry + validações (sobreposição, limite do dia)
│   │   └── period.py         ⏳ Period (semana/mês), PeriodStatus e transições
│   ├── storage/              ⏳ db.py, migrations/, *_repo.py
│   ├── auth/                 ⏳ hash de senha, sessão
│   ├── services/             ⏳ users, projects, entries, approval, audit
│   ├── reports/              ⏳ horas por pessoa/projeto/período, exportação
│   ├── integrations/         ⏳ excel/, email/
│   └── ui/                   ⏳ login, minha semana, aprovação, cadastros, relatórios
└── tests/                    ⏳ domain, services (inclui permissões), UI smoke
```

## Segurança (mínimo desde a Fase 1)
- Senhas com hash (scrypt/argon2) + bloqueio após N tentativas.
- Primeiro acesso: admin inicial com senha trocada obrigatoriamente.
- Toda rota/ação passa pelo `services` com o usuário da sessão.
- HTTPS obrigatório se a opção B (nuvem) for escolhida.
- Dados pessoais (nome, horas) → LGPD: acesso só por papel; exportação registrada na auditoria.
