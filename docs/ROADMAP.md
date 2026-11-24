# ROADMAP — Objetivos e fases

## Status atual
- **Fase:** 1 — MVP. **Fundação pronta** (2026-11-23, branch `feature/fundacao`): login, primeiro acesso,
  papéis, colaboradores, projetos, auditoria, pacote portátil validado (abre isolado do Python do PC). 60 testes ok.
  App **sem nenhuma dependência** (só biblioteca padrão), por pedido do usuário.
- **Repositório:** github.com/Hnrqmeans/ApontarHoras — **público**: nada de dado real, caminho pessoal, e-mail ou
  segredo nos arquivos; commits com o e-mail `noreply` do GitHub (config local do repositório).
- **Escopo definido (2026-11-23):** apontamento de horas para a **Lei do Bem**. Colaborador aponta horas nos
  projetos; no fim do mês um **responsável** acessa, confere e exporta. **Nada complexo por enquanto** (sem fluxo
  de aprovação, sem gestores, sem cronômetro).
- **Apontamento pronto (2026-11-24, branch `feature/apontamento`):** modelo tirado da planilha antiga (DOMAIN ›
  Planilha antiga): tarefas com Lei do Bem, início/término com almoço, sem sobreposição, "Meus apontamentos" com
  lacunas contra a jornada. 102 testes ok. Exclusão com horas bloqueada (só desativar).
- **Fase 1 completa em código (2026-11-24, branch `feature/confianca`):** relatório + painel + pendências da equipe,
  conferência do mês sem trava (D9), Excel/PDF com selo, auditoria encadeada, motivo nas correções do responsável,
  lançamento tardio, recuperação de acesso, feriados, importar projetos, porta exclusiva. 170 testes ok; carga
  20×20 = 400/400 gravados, 0 falhas.
- **Versão:** fica em **v0.1.0** até alguém testar de verdade (pedido do usuário, 2026-11-24): sem tag, sem `main`.
- **Arquitetura (D1, 2026-11-23):** servidor da empresa; remotos pela VPN. Usuário vai levar o checklist à TI.
- **Próximo:** teste manual do usuário e demonstração ao responsável; respostas da TI (D10); instalação no servidor.
- **Bloqueios:** teste manual; TI (D10).
- **Última atualização:** 2026-11-24

> IA: leia só esta seção no início da rotina. O restante é consulta sob demanda.

---

## Decisões
| #  | Pergunta                                                         | Situação |
|----|------------------------------------------------------------------|----------|
| D1 | **Como as horas de todos chegam ao responsável?**                | ✅ **Servidor da empresa** (2026-11-23): o app roda nele; todos gravam lá; responsável exporta tudo. Remotos via **VPN**. Pendente: checklist com a TI (ARCHITECTURE › Servidor da empresa). |
| D2 | Funcionar sem rede?                                              | ✅ Não: precisa de rede da empresa ou VPN. |
| D3 | Timesheet ou ponto eletrônico?                                   | ✅ **Timesheet de projetos para a Lei do Bem** (não é controle de jornada). |
| D4 | Login                                                            | Simples (usuário/senha) — confirmar após D1. |
| D5 | Papéis                                                           | ✅ **colaborador** + **responsável** (admin). Gestor/aprovação: backlog. |
| D6 | Forma de apontar                                                 | ✅ Como a planilha (2026-11-24): início/término por atividade, tarefa define a Lei do Bem. |
| D7 | Executável ou navegador para o colaborador?                      | ✅ Navegador (o .exe roda só no servidor). |
| D8 | Dependências                                                     | ✅ **Nenhuma** no app (2026-11-23): só biblioteca padrão; abre em máquina limpa. |
| D9 | Travar o mês?                                                    | ✅ **Não** (2026-11-24): quem está em campo ou sem treinamento não pode perder os dias. Confiança pelo **rastro** (auditoria, lançamento tardio sinalizado, conferência), não por bloqueio. |
| D10 | O que a TI já tem (ponto, ERP, AD, HTTPS, backup)?              | ⏳ Perguntas com o usuário (2026-11-24). Se houver ponto/ERP, exportação e lacunas podem integrar com ele. |

---

## Fases

### Fase 1 — MVP "apontar e entregar o mês"
- [x] Projeto Python (pyproject sem dependências, ruff, pytest, CI), camadas `domain/storage/services/web` — 2026-11-23
- [x] Login, primeiro acesso (cria o responsável), senha temporária, bloqueio por tentativas, sessões — 2026-11-23
- [x] Cadastros (responsável): colaboradores (redefinir senha, desativar, excluir), projetos de P&D — 2026-11-23
- [x] Auditoria (tela só do responsável) — 2026-11-23
- [x] Pacote portátil Windows (`ApontarHoras.exe` + `ApontarHoras.ini`), validado isolado — 2026-11-23
- [x] Tarefas (Lei do Bem) + projeto elegível ou não — 2026-11-24
- [x] Colaborador: apontar (início/término/almoço), corrigir, excluir, mês com totais e lacunas — 2026-11-24
- [x] Responsável: relatório com filtros + painel; pendências da equipe; **conferir o mês** (sem travar, D9);
  exportar Excel/PDF com selo — 2026-11-24
- [x] Confiança: lançamento tardio, motivo nas correções do responsável, auditoria encadeada + Verificar integridade,
  recuperação de acesso pelo servidor, aviso de responsável único, `docs/SEGURANCA.md` — 2026-11-24
- [x] Implantação: importar projetos colando a lista, feriados (nacionais + Sexta-feira Santa), ícone da aba,
  teste de carga (`scripts/carga.py`), porta exclusiva e fila de conexões 64 — 2026-11-24
- [x] Bloquear exclusão de usuário/projeto/tarefa com horas apontadas (só desativar) — 2026-11-24
- [ ] Instalação no servidor da empresa (com a TI)

### Depois (só se fizer falta)
- Fluxo de aprovação/devolução; gestores por equipe; relatório anual para o FORMP&D; anexos de evidência;
  lembrete de apontamento; cronômetro; SSO; nuvem.
