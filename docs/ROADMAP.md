# ROADMAP — Objetivos e fases

## Status atual
- **Fase:** 0 — Planejamento. Estrutura de documentação criada (2026-11-23), modelada no projeto Pagodinho.
- **Repositório:** github.com/Hnrqmeans/ApontarHoras — **público**: nada de dado real, caminho pessoal, e-mail ou
  segredo nos arquivos; commits com o e-mail `noreply` do GitHub (config local do repositório).
- **Escopo definido (2026-11-23):** apontamento de horas para a **Lei do Bem**. Colaborador aponta horas nos
  projetos; no fim do mês um **responsável** acessa, confere e exporta. **Nada complexo por enquanto** (sem fluxo
  de aprovação, sem gestores, sem cronômetro).
- **Aguardando:** exemplo do usuário de como é o apontamento hoje (prometido para 2026-11-24) → ajustar DOMAIN.
- **Arquitetura (D1, 2026-11-23):** servidor da empresa; remotos pela VPN. Usuário vai levar o checklist à TI.
- **Próximo:** com o exemplo → Fase 1 (MVP). Dá para começar o código antes da resposta da TI (roda local no dev).
- **Bloqueios:** exemplo do usuário.
- **Última atualização:** 2026-11-23

> IA: leia só esta seção no início da rotina. O restante é consulta sob demanda.

---

## Decisões
| #  | Pergunta                                                         | Situação |
|----|------------------------------------------------------------------|----------|
| D1 | **Como as horas de todos chegam ao responsável?**                | ✅ **Servidor da empresa** (2026-11-23): o app roda nele; todos gravam lá; responsável exporta tudo. Remotos via **VPN**. Pendente: checklist com a TI (ARCHITECTURE › Servidor da empresa). |
| D2 | Funcionar sem rede?                                              | ✅ Não: precisa de rede da empresa ou VPN. |
| D7 | Colaborador usa **executável** ou **link no navegador**?         | Em aberto: com servidor, o navegador já basta (nada a instalar); executável = janela que abre o mesmo endereço. |
| D3 | Timesheet ou ponto eletrônico?                                   | ✅ **Timesheet de projetos para a Lei do Bem** (não é controle de jornada). |
| D4 | Login                                                            | Simples (usuário/senha) — confirmar após D1. |
| D5 | Papéis                                                           | ✅ **colaborador** + **responsável** (admin). Gestor/aprovação: backlog. |
| D6 | Forma de apontar                                                 | Aguardando o exemplo do usuário. |

---

## Fases

### Fase 1 — MVP "apontar e entregar o mês"
- [ ] Projeto Python (pyproject, ruff, pytest), camadas `domain/storage/services/ui`
- [ ] Cadastros mínimos (responsável): colaboradores, projetos de P&D
- [ ] Colaborador: apontar horas (data, projeto, horas, descrição da atividade), ver/editar o mês, total do mês
- [ ] Responsável: ver horas do mês por pessoa e por projeto; **fechar o mês** (trava edição); exportar Excel
- [ ] Executável Windows (mesma técnica do Pagodinho)

### Depois (só se fizer falta)
- Fluxo de aprovação/devolução; gestores por equipe; relatório anual para o FORMP&D; anexos de evidência;
  lembrete de apontamento; cronômetro; SSO; nuvem.
