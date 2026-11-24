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

## 2026-11-24 — Fase 1 completa: confiança, relatório e implantação (3 frentes em paralelo)  `#feat #seguranca #relatorio`
**Fase:** 1 — MVP
**Pedido:** "implementar tudo que falta", com agentes em paralelo; versão continua v0.1.0 (ninguém testou ainda).
**Como:** 3 worktrees (`feature/confianca-rastro`, `feature/relatorio`, `feature/implantacao`) com migrações
reservadas (003/004/005), merge em `feature/confianca`. Conflitos só em listas (rotas, menu, Início) e na regra de
dias: `summarize_days` (extraída de `month_summary`) passou a receber os feriados → "Meus apontamentos" e
"Pendências da equipe" usam a mesma regra.
**O que mudou:**
- Confiança: lançamento tardio sinalizado; motivo obrigatório quando o responsável corrige/exclui horas de outra
  pessoa; auditoria encadeada (migração 003) + Auditoria › Verificar integridade; `apontarhoras.recuperar` +
  `RecuperarAcesso.bat`; aviso de responsável único; `docs/SEGURANCA.md`.
- Responsável: `/relatorio` (filtros da planilha, totais, painel em barras CSS), `/relatorio/pendencias`,
  conferência do mês sem trava (migração 004, selo SHA-256, "alterado após a conferência"), Excel (`integrations/xlsx`)
  e impressão/PDF com selo; exportações auditadas.
- Implantação: importar projetos colando a lista; feriados (migração 005, nacionais + Sexta-feira Santa); favicon;
  `scripts/carga.py` + `tests/test_concorrencia.py`; CI passa a fazer lint de `scripts/`.
- Servidor: fila de conexões 64 (a padrão, 5, causava esperas de ~1 s com 20 pessoas).
**Bug evitado:** `ApontarHoras.exe -m módulo` sem argumentos subiria o servidor (sitecustomize via `['-m']`).
**Verificado:** 170 testes + ruff ok; carga 20×20 no código integrado: 400/400 gravados, 0 duplicados, 0 falhas;
GET máx. 85 ms (antes ~1 s).
**Limitações conhecidas:** re-salvar sem mudar marca "alterado após a conferência" (o selo não muda); recarregar a
impressão grava nova auditoria; apagar os últimos registros da auditoria só se detecta com o selo anotado fora.
**Pendências:** teste manual; D10 (TI); instalação no servidor; jornada por pessoa.

## 2026-11-24 — Mês sem trava (D9) + porta exclusiva  `#decisao #fix`
**Fase:** 1 — MVP
**Decisão D9:** o mês **não trava**: quem está em campo ou sem treinamento não pode perder os dias. Confiança
pelo rastro (auditoria, lançamento tardio sinalizado, conferência do responsável). DOMAIN e ROADMAP atualizados.
**Bug (pergunta do usuário: "e se o servidor já roda outro .exe/localhost?"):** no Windows, o `SO_REUSEADDR`
padrão do `http.server` deixava uma 2ª cópia do app subir na **mesma porta** sem erro (requisições divididas entre
as duas; com pastas de dados diferentes, horas em dois bancos) → `AppServer` usa `SO_EXCLUSIVEADDRUSE` no Windows
→ a 2ª cópia falha com "porta em uso". Teste `test_second_instance_cannot_share_port`. 104 testes + ruff ok.
**Arquivos:** `web/server.py`, `tests/test_web.py`, `docs/DOMAIN.md`, `docs/ROADMAP.md`.

## 2026-11-24 — Apontamento a partir da planilha antiga  `#feat #decisao`
**Fase:** 1 — MVP
**Pedido:** usuário trouxe a planilha usada hoje ("copiar os modelos e melhorar o que for necessário").
**Análise:** lida pelo XML e pelo VBA extraído (5 formulários). Regras resumidas em DOMAIN › Planilha antiga.
Dados reais (nomes, clientes) e a senha de proteção do VBA **não** foram copiados para o repositório (público).
**Decisões:** D6 = início/término por atividade, como na planilha; operador = usuário logado; Lei do Bem =
projeto elegível **e** tarefa elegível, guardada no apontamento; edição permitida (a planilha só excluía).
**O que mudou:**
- `domain`: `task.py`, `time_entry.py` (horário, almoço, duração, sobreposição, data, mês), `workday.py` (jornada).
- `storage`: migração `002_apontamentos.sql` (tasks com as 9 da planilha, `projects.rd_eligible`,
  `time_entries` com RESTRICT), `tasks_repo`, `time_entries_repo`.
- `services`: `tasks_service`, `time_entries_service` (permissão dono/responsável, auditoria, resumo do mês);
  exclusão de usuário/projeto/tarefa com horas bloqueada.
- `web`: telas Meus apontamentos (mês dia a dia, totais, lacunas), Novo/Corrigir/Excluir apontamento, Tarefas;
  projeto ganhou "Conta para a Lei do Bem"; Início com atalhos para todos; `date_field`, `select_field` com
  placeholder; `.gitignore` ignora `*.xlsm`/`*.xls`.
**Verificado:** 102 testes ok (Python 3.12 do Cygwin com `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; a `.venv` não foi
criada nesta sessão); depois, na `.venv` do usuário: 103 testes + ruff ok.
**Bug corrigido (teste manual do usuário):** "Primeiro acesso" dava 403 "Formulário enviado de outro site" →
`Referrer-Policy: no-referrer` faz Edge/Chrome mandarem `Origin: null` no POST, e a trava de origem recusa
`null` (os testes não pegavam: urllib não manda `Origin`) → política trocada para `same-origin` + teste
`test_browser_origin_is_accepted` simulando o navegador. Afetava todos os formulários desde a fundação.
**Pendências / próximos passos:**
- Visão do responsável + fechamento do mês + exportação (Excel/PDF), com os filtros da planilha.
- Importar projetos da planilha; feriados; jornada por pessoa; teste de carga com 20 usuários.

## 2026-11-23 — Teste exploratório do pacote + guia da rotina para a equipe  `#test #docs`
**Fase:** 1 — MVP
**O que foi feito:** pacote (`dist\ApontarHoras`) rodando isolado (porta 8766, dados temporários) e navegado como
responsável e colaboradores: 61/61 verificações (primeiro acesso, cadastros, troca obrigatória de senha, 403 do
colaborador inclusive por POST direto, bloqueio 5× e desbloqueio, desativar derruba a sessão, exclusão em 2 cliques,
auditoria completa e sem senhas, CSRF, Origin, envio > 1 MB, travessia de pasta, cookie inventado, 15 gravações
simultâneas). Nenhum erro no log do servidor. Prints conferidos (tema claro e escuro).
**Ajuste:** `style.css` — parágrafos dentro de formulários sem margem extra (confirmação de exclusão ficava espaçada).
**Guia para a equipe:** documento "ApontarHoras — Como funciona a rotina" (claude.ai, fora do repositório) com ciclo
do mês, passo a passo do colaborador e do responsável, segurança, situação e perguntas para a equipe decidir.

## 2026-11-23 — Fundação: login, papéis, cadastros, auditoria, pacote portátil (sem dependências)  `#feat #infra #decisao`
**Fase:** 1 — MVP
**Pedido:** "não gere dependências, o app deve abrir em uma máquina limpa"; depois subir na branch remota.
**Decisão:** NiceGUI descartado → só biblioteca padrão: `http.server` (ThreadingHTTPServer) + `sqlite3` (WAL) +
HTML gerado no servidor, sem JavaScript (CSP `script-src 'none'`). pytest/ruff só no extra `[dev]`.
**O que mudou:**
- `domain`: erros, duração (minutos ⇄ H:MM), usuário/papel/bloqueio, projeto, auditoria (`changes`).
- `auth`: scrypt; token de sessão (banco guarda o SHA-256); anti-CSRF derivado do token.
- `storage`: `Database`/`transaction`/`migrate` + `001_init.sql` (users, sessions, projects, audit_log); repositórios.
- `services`: primeiro acesso, login (5 erros → 15 min), sessão 12 h, trocar senha; usuários (≥ 1 responsável,
  senha temporária obriga troca); projetos; auditoria. Permissão conferida aqui.
- `web`: despacho com travas (login, troca obrigatória de senha, papel, CSRF, origem), cabeçalhos de segurança,
  telas Primeiro acesso / Entrar / Trocar senha / Início / Colaboradores / Projetos / Auditoria; exclusão em 2 cliques.
- Pacote: `scripts/build.ps1` (Python 3.12.10 embeddable, SHA-256 + assinatura) e `sitecustomize.py`.
**Bug encontrado no teste do pacote:** `ApontarHoras.exe --sem-navegador` → "unknown option" → o Python embutido
interpreta opções `--` antes do app → configuração passou para `ApontarHoras.ini` ao lado do .exe
(`main.load_settings`: padrão ← .ini ← linha de comando); o .exe só abre sem argumentos.
**Verificado:** 60 testes + ruff ok; nenhum import fora da biblioteca padrão (varredura com `sys.stdlib_module_names`);
pacote gerado e executado isolado (tela de primeiro acesso, CSS e banco criados).
**Arquivos:** `src/apontarhoras/**`, `tests/**`, `pyproject.toml`, `scripts/**`, `.github/workflows/ci.yml`, docs.
**Pendências / próximos passos:**
- Exemplo do usuário → apontamento, fechamento do mês, exportação Excel/PDF (sem bibliotecas).
- Bloquear exclusão de usuário/projeto com horas (quando existirem apontamentos).
- Combinar com a TI: porta, nome do servidor, início automático, backup, HTTPS.

## 2026-11-23 — D1: servidor da empresa + VPN  `#decisao`
**Fase:** 0 — Planejamento
**Motivo:** usuário quer que uma pessoa só baixe os dados de todos, sem envio de arquivos; a empresa tem servidor e
os remotos usam VPN.
**O que mudou:** D1/D2 decididas; nova D7 (executável × navegador); checklist para a TI em ARCHITECTURE;
`.gitignore` passa a ignorar `exemplos/` e `*.pdf` (arquivo de exemplo do usuário com dados reais).
**Pendências / próximos passos:** exemplo do usuário; resposta da TI; D7.

## 2026-11-23 — Escopo: apontamento para a Lei do Bem, versão simples  `#decisao #docs`
**Fase:** 0 — Planejamento
**Motivo:** usuário: "a ideia é apontar horas e no final do mês um responsável ter acesso… é um apontamento para
lei do bem, então não vamos criar nada complexo ainda".
**O que mudou:** ROADMAP reduzido a um MVP (apontar → responsável fecha e exporta o mês); D3 e D5 decididas;
aprovação/gestores/cronômetro foram para "Depois". DOMAIN ganhou a seção "Contexto: Lei do Bem". CLAUDE.md atualizado.
**Pendências / próximos passos:**
- Usuário envia exemplo do apontamento atual (2026-11-24) → definir campos e forma de apontar (D6).
- Decidir D1 (como as horas chegam ao responsável).

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
