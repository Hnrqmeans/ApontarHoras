# DEVLOG — Diário de implementação

> Entradas em ordem **decrescente** (mais recente no topo). IA: leia só a primeira entrada.
> Para histórico, busque por tag: `#feat #fix #refactor #docs #decisao #infra`.

<!--
MODELO DE ENTRADA (copiar e colar no topo, abaixo desta linha)

## AAAA-MM-DD — Título curto  `#tag`
**Fase:** N — nome
**Objetivo:** o que se queria alcançar.
**Motivo:** por que foi feito agora / problema que resolve.
**O que mudou:**
- item
**Arquivos:** `caminho/arquivo.py`, ...
**Bugs corrigidos:** (se houver) sintoma → causa → correção.
**Pendências / próximos passos:**
- item
-->

## 2026-11-23 — Repositório conectado e revisão de dados sensíveis  `#infra`
**Fase:** 0 — Planejamento
**Objetivo:** ligar a pasta ao GitHub e subir a estrutura sem expor dados pessoais.
**O que mudou:**
- `git init` + `origin` = github.com/Hnrqmeans/ApontarHoras (já tinha 1 commit com README); `main` local = `origin/main`.
- Repositório é **público** → removido caminho pessoal de `docs/DESENVOLVEDOR.md`; autor dos commits configurado
  só neste repositório com o e-mail `noreply` do GitHub; `.gitignore` reforçado (`.env*`, chaves,
  `.claude/settings.local.json`, planilhas/CSV com dados reais).
- Branch `dev` criada; estrutura entrou por `feature/estrutura-inicial` (fluxo do CLAUDE.md).
**Arquivos:** `.gitignore`, `docs/DESENVOLVEDOR.md`, `docs/ROADMAP.md`, `docs/DEVLOG.md`
**Pendências / próximos passos:**
- Decisões D1–D6 (ROADMAP) para iniciar a Fase 1.

## 2026-11-23 — Início do projeto: estrutura de documentação  `#docs #decisao`
**Fase:** 0 — Planejamento
**Objetivo:** criar o esqueleto do projeto no mesmo padrão do Pagodinho (CLAUDE.md curto + `docs/`).
**Motivo:** pedido do usuário: app executável para apontar horas, com dados de toda a equipe e gestão por um admin.
**O que mudou:**
- `CLAUDE.md`, `README.md`, `.gitignore`
- `docs/ROADMAP.md` (decisões em aberto D1–D6 + fases propostas), `docs/ARCHITECTURE.md` (opções de arquitetura,
  camadas, mapa de módulos planejado), `docs/DOMAIN.md` (conceitos, estados do período, permissões),
  `docs/DESENVOLVEDOR.md` (esqueleto)
**Pendências / próximos passos:**
- Responder D1–D6 com o usuário; depois iniciar a Fase 1.
