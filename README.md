# ApontarHoras

[![CI](https://github.com/Hnrqmeans/ApontarHoras/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Hnrqmeans/ApontarHoras/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Dependências](https://img.shields.io/badge/depend%C3%AAncias-nenhuma-brightgreen)
![Versão](https://img.shields.io/badge/vers%C3%A3o-0.1.0%20(teste)-orange)

**Apontamento de horas em projetos de P&D, com a evidência que a Lei do Bem pede.**

A equipe aponta as horas pelo navegador, na rede da empresa ou pela VPN. No fim do mês, um responsável confere,
marca o mês como conferido e exporta o relatório em Excel ou PDF. Tudo fica num servidor interno, com histórico
de cada alteração.

> **Status:** v0.1.0 — funcionalidades da Fase 1 completas e testadas automaticamente; **aguardando o primeiro
> teste com usuários**. Ver [roadmap](docs/ROADMAP.md).

---

## Sumário
- [Funcionalidades](#funcionalidades)
- [Como funciona](#como-funciona)
- [Início rápido](#início-rápido)
- [Instalação no servidor](#instalação-no-servidor)
- [Segurança](#segurança)
- [Desenvolvimento](#desenvolvimento)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Documentação](#documentação)

## Funcionalidades

**Para quem aponta**
- Apontamento por data, projeto, tarefa, início e término (aceita `7`, `730` ou `7:30`), com a pergunta do almoço.
- Validações na hora: sem sobreposição de horários, sem data futura, descrição obrigatória quando a hora conta para
  a Lei do Bem.
- "Meus apontamentos": o mês dia a dia contra a jornada — **OK**, **Pendência**, **Verificar** e feriados.
- O mês não trava: quem estava em campo lança depois, e o apontamento é marcado como lançado depois do mês.

**Para o responsável**
- Cadastros de colaboradores, projetos (inclusive colando a lista de uma planilha), tarefas e feriados.
- Relatório com filtros por período, colaborador, projeto, tarefa e tipo (Lei do Bem / não elegível), com totais e
  painel por projeto, tarefa e colaborador.
- Pendências da equipe no mês, antes de conferir.
- Conferência do mês com selo SHA-256: o que mudar depois aparece como "alterado após a conferência".
- Exportação para **Excel (.xlsx)** e **PDF** (impressão do navegador), com selo de conferência.

**Rastro e confiança**
- Auditoria de todas as ações, **encadeada** (cada registro sela o anterior), com a tela *Verificar integridade*.
- Correção de horas de outra pessoa só com motivo registrado.
- Quem tem horas apontadas não pode ser excluído, só desativado.

## Como funciona

```
 Navegador da equipe ──rede interna / VPN──►  Servidor: ApontarHoras.exe ──► apontarhoras.db (com backup)
```

- **Zero dependências:** só a biblioteca padrão do Python (`http.server` + `sqlite3`), páginas geradas no servidor e
  nenhum JavaScript. O pacote para Windows leva o Python oficial embutido e roda em máquina limpa.
- **Papéis:** *colaborador* (só os próprios dados) e *responsável* (cadastros, relatório, conferência e auditoria).
- **Banco:** SQLite em modo WAL; escritas simultâneas aguardam a vez em vez de falhar. Medido: 20 pessoas × 20
  apontamentos simultâneos, 400/400 gravados, 0 falhas.

## Início rápido

Requisitos: Windows e Python 3.12 (só para desenvolver; o pacote final já traz o Python).

```powershell
git clone https://github.com/Hnrqmeans/ApontarHoras.git
cd ApontarHoras
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"      # instala só pytest e ruff; o app não tem dependências
.\.venv\Scripts\python.exe -m apontarhoras --dados .\dados-dev --porta 8090
```

Abra `http://localhost:8090`. Com o banco vazio, a primeira tela cria o **responsável**; depois, cadastre os
projetos e os colaboradores (cada um recebe uma senha temporária e a troca no primeiro acesso).

## Instalação no servidor

1. Gerar o pacote: `.\scripts\build.ps1` → `dist\ApontarHoras-vX.Y.Z-windows.zip`.
2. Descompactar no servidor e ajustar o `ApontarHoras.ini`: `rede = sim`, a porta e a pasta de dados (com backup).
3. Liberar a porta no firewall **somente para a rede interna e a VPN**.
4. Iniciar com o Windows (Agendador de Tarefas ou serviço), uma única instância.

Detalhes, atualização de versão e recuperação de acesso: [docs/DESENVOLVEDOR.md](docs/DESENVOLVEDOR.md).

## Segurança

- Senhas com `scrypt`; sessões guardadas apenas como hash; bloqueio após 5 tentativas erradas.
- Proteção contra CSRF e verificação de origem nos formulários; CSP sem scripts; cabeçalhos de segurança.
- Permissões verificadas no servidor em toda operação, não só escondendo botões.
- Auditoria encadeada detecta alteração direta no arquivo do banco.
- Recomendado: HTTPS interno (proxy com certificado da empresa) e pasta de dados acessível só ao serviço e à TI.

Visão completa para o responsável e a TI: [docs/SEGURANCA.md](docs/SEGURANCA.md).

## Desenvolvimento

```powershell
.\.venv\Scripts\python.exe -m pytest                          # testes (unitários e ponta a ponta)
.\.venv\Scripts\python.exe -m ruff check src tests scripts    # lint
.\.venv\Scripts\python.exe scripts\carga.py                   # teste de carga (20 × 20, banco temporário)
```

- Camadas: `web → services → storage`, com `domain` puro (regras sem I/O). Permissão sempre conferida nos services.
- Fluxo de git: trabalho em `feature/*` a partir da `dev`; a `dev` só recebe código com todos os testes passando;
  a `main` recebe versões.
- Regras de código e convenções: [CLAUDE.md](CLAUDE.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Estrutura do projeto

```
src/apontarhoras/
├── domain/        regras puras: apontamento, jornada, feriados, relatório, auditoria encadeada
├── storage/       SQLite, repositórios e migrações numeradas
├── services/      casos de uso, permissões e auditoria
├── integrations/  geração de Excel (.xlsx) sem bibliotecas
└── web/           servidor HTTP, telas e estilos
scripts/           build do pacote portátil, teste de carga, recuperação de acesso
tests/             pytest: domínio, serviços, web ponta a ponta, concorrência
docs/              documentação do projeto
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [ROADMAP](docs/ROADMAP.md) | Status, decisões e próximos passos |
| [DOMAIN](docs/DOMAIN.md) | Regras de negócio (apontamento, jornada, relatório, auditoria) |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Camadas, módulos e decisões técnicas |
| [SEGURANCA](docs/SEGURANCA.md) | Dados, acessos, backup e checklist para a TI |
| [DESENVOLVEDOR](docs/DESENVOLVEDOR.md) | Ambiente, build, instalação, versões |
| [DEVLOG](docs/DEVLOG.md) | Diário de implementação |
