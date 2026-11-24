# ROADMAP — Objetivos e fases

## Status atual
- **Fase:** 0 — Planejamento. Estrutura de documentação criada (2026-11-23), modelada no projeto Pagodinho.
- **Repositório:** github.com/Hnrqmeans/ApontarHoras — **público**: nada de dado real, caminho pessoal, e-mail ou
  segredo nos arquivos; commits com o e-mail `noreply` do GitHub (config local do repositório).
- **Em andamento:** fechar as **Decisões em aberto** (abaixo) com o usuário antes de escrever código.
- **Próximo:** com as decisões tomadas → Fase 1 (fundação: projeto Python, banco, login, papéis).
- **Bloqueios:** decisões D1–D6.
- **Última atualização:** 2026-11-23

> IA: leia só esta seção no início da rotina. O restante é consulta sob demanda.

---

## Decisões em aberto (responder antes da Fase 1)
| #  | Pergunta                                                                                     | Proposta / recomendação |
|----|----------------------------------------------------------------------------------------------|-------------------------|
| D1 | **Onde ficam os dados de todos?** (a) servidor na rede da empresa; (b) nuvem; (c) pasta compartilhada (OneDrive/rede) com arquivo por pessoa e o admin consolida | **(a) ou (b)**: um servidor central. (c) é o mais simples de instalar, mas sem tempo real e com risco de conflito. Ver ARCHITECTURE › Opções de arquitetura. |
| D2 | O app precisa funcionar **sem internet/rede** (apontar offline e enviar depois)?             | Começar **online**; offline só se for requisito. |
| D3 | É **apontamento de horas por projeto** (timesheet) ou **controle de jornada/ponto** (entrada/saída, valor legal)? | Timesheet. Ponto eletrônico tem regras legais próprias (Portaria MTP 671/2021) — fora do escopo, salvo decisão contrária. |
| D4 | **Login**: usuário/senha próprio do app, ou conta da empresa (Windows/AD/Microsoft 365)?     | Usuário/senha no início; SSO depois, se pedido. |
| D5 | Papéis: só **admin + colaborador**, ou também **gestor** (aprova a própria equipe)?          | Três papéis (admin, gestor, colaborador). |
| D6 | Forma de apontar: **início/fim** (relógio), **duração** por dia, ou **cronômetro**?          | Duração por dia em grade semanal + início/fim opcional; cronômetro numa fase posterior. |

Outras perguntas (não bloqueiam): quantas pessoas usam? Há clientes/centros de custo? Precisa de exportação para
Excel/ERP/folha? Jornada esperada por pessoa (ex.: 8h/dia) para mostrar horas faltantes? Período de fechamento
(semanal, quinzenal, mensal)?

---

## Fases (proposta — ajustar depois das decisões)

### Fase 1 — Fundação
- [ ] Projeto Python (pyproject, ruff, pytest, CI), camadas `domain/storage/services/ui`
- [ ] Banco + migrações; usuário admin inicial criado na primeira execução
- [ ] Login, sessão, troca de senha; papéis e checagem de permissão no `services`
- [ ] Auditoria (quem/quando/o quê)

### Fase 2 — Cadastros (admin)
- [ ] Usuários (criar, desativar, redefinir senha, papel, equipe, jornada esperada)
- [ ] Equipes e gestores
- [ ] Clientes, projetos, atividades/tipos de hora; projeto ativo/inativo; quem pode apontar em qual projeto

### Fase 3 — Apontamento (colaborador)
- [ ] Grade semanal (dias × projeto/atividade), totais por dia e semana, horas esperadas × apontadas
- [ ] Lançamento avulso (data, projeto, atividade, duração ou início/fim, descrição)
- [ ] Copiar semana anterior; validações (sobreposição, dia acima do limite, data futura)
- [ ] **Enviar** período para aprovação

### Fase 4 — Aprovação e fechamento (gestor/admin)
- [ ] Fila de períodos enviados; aprovar / devolver com motivo
- [ ] Fechar período (bloqueia edição); reabrir com motivo
- [ ] Pendências: quem não enviou / não apontou

### Fase 5 — Relatórios e exportação
- [ ] Horas por pessoa, projeto, cliente, atividade, período; gráficos
- [ ] Exportar Excel/CSV/PDF
- [ ] Painel do gestor

### Fase 6 — Executável e implantação
- [ ] Pacote Windows (mesma técnica do Pagodinho: Python embeddable assinado)
- [ ] Instalação do servidor (conforme D1) e backup automático do banco
- [ ] Guia de instalação para a TI da empresa

### Backlog
- Cronômetro; lembrete de apontamento; offline com sincronização; SSO/AD; integração com ERP/folha;
  banco de horas; app no celular (navegador).
