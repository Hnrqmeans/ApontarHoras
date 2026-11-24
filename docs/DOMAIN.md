# DOMAIN — Conceitos e regras de apontamento

> Fonte da verdade das regras de negócio. Rascunho de 2026-11-23 — confirmar com o usuário (ROADMAP › D1–D6).

## Contexto: Lei do Bem (2026-11-23)
O app serve para registrar as horas que cada colaborador dedica a **projetos de P&D/inovação**, como evidência para
a Lei do Bem (Lei 11.196/2005). Uso: o colaborador aponta durante o mês; no fim do mês o **responsável** confere,
fecha e exporta. Por isso, cada apontamento precisa de **descrição da atividade** (o que foi feito no projeto) e os
dados de meses já conferidos não podem mudar sem registro.

**MVP (Fase 1):** papéis só `colaborador` e `responsável` (= admin); o mês **não trava** (D9, 2026-11-24): lançar ou corrigir depois da virada do mês é permitido e fica rastreado.
As tabelas abaixo com `gestor`, `enviado`, `devolvido` e `aprovado` são a versão completa, **para depois**.

## Planilha antiga (referência, analisada em 2026-11-24)
Fonte do modelo: planilha de apontamentos de P&D usada hoje pela equipe (arquivo fora do git: tem dados reais).
- **Tabela de apontamentos:** ID, data, operador, projeto, Grau P&D (1/0), tarefa, início, término, horas, mês,
  observações. **Listas:** projetos (`código - cliente - nome`), operadores, tarefas com Grau P&D.
- **Formulário de apontamento (VBA):** sem data futura; operador/projeto/tarefa só da lista; horário aceita
  `7`, `730`, `7:30`; término > início; **sem sobreposição** no mesmo dia; período que começa antes das 12:00 e
  termina depois das 13:00 **pergunta** se desconta 1 h de almoço; Grau P&D vem da **tarefa** (projeto
  "Tarefas Internas" = 0); **observação obrigatória quando Grau P&D = 1**.
- **Inconsistências:** por operador e período, compara o apontado com a jornada (seg–qui 8h27, sex 7h42) →
  OK / Pendência / Verificar. **Relatório:** filtros (operador, projeto, Lei do Bem/não elegível, período),
  totais Lei do Bem × não elegível, PDF. **Painel:** horas totais, % Lei do Bem, horas por projeto e por tarefa.
- **Fraquezas que o app corrige:** qualquer pessoa aponta em nome de outra; não há edição (só excluir e
  relançar); sem auditoria nem fechamento do mês; senha de proteção dentro do VBA; arquivo único sem controle de
  acesso simultâneo; Grau P&D antigo fica divergente da lista atual sem explicação.

## Conceitos
| Conceito         | Descrição                                                                                     |
|------------------|-----------------------------------------------------------------------------------------------|
| **Usuário**      | Pessoa que acessa o app: nome, login, e-mail, papel, equipe, jornada esperada, ativo/inativo. |
| **Papel**        | `admin` (tudo), `gestor` (aprova e vê a própria equipe), `colaborador` (só os próprios dados). |
| **Equipe**       | Grupo de usuários com um ou mais gestores.                                                    |
| **Cliente**      | (Opcional) para quem o projeto é feito.                                                       |
| **Projeto**      | Onde as horas são apontadas: código, nome, cliente, ativo, quem pode apontar.                 |
| **Tarefa**       | Tipo de atividade (Desenvolvimento, Suporte…); define se a hora conta para a Lei do Bem.      |
| **Apontamento**  | Registro de horas: usuário, data, projeto, atividade, duração (min), início/fim opcionais, descrição. |
| **Período**      | Intervalo enviado para aprovação de uma vez (proposta: semana seg–dom).                       |
| **Jornada esperada** | Minutos previstos por dia útil (ex.: 480). Base para "horas faltantes".                   |

## Regras
### Apontamento (implementado 2026-11-24, regras da planilha antiga)
- Campos: data, projeto, tarefa, **início e término** (obrigatórios), almoço, descrição. Sempre em nome do
  **usuário logado** (ninguém aponta por outra pessoa).
- Horário aceita `7`, `07`, `730`, `7:30`, `7h30`; vai de 00:00 a 23:59 (sem virar a noite). Término > início.
- Começa antes das 12:00 e termina depois das 13:00 → **obrigatório escolher**: descontar 1 h ou "sem intervalo".
  Horas = término − início − intervalo (minutos inteiros).
- Sem sobreposição com outro apontamento da mesma pessoa no mesmo dia (encostar pode: 12:00–13:00 após 08:00–12:00).
- Sem data futura. Só projeto e tarefa **ativos** (na correção, os que o apontamento já tinha continuam valendo).
- **Lei do Bem** = projeto elegível **e** tarefa elegível. Guardado no apontamento (retrato da época): mudar o
  cadastro depois não muda os apontamentos já feitos; corrigir só horário/descrição mantém o valor gravado.
- **Descrição obrigatória quando conta para a Lei do Bem** (é a evidência); até 1000 caracteres.
- Corrigir/excluir: o dono ou o responsável (o apontamento continua sendo do dono). Tudo auditado.
- **O mês não trava** (D9): quem estava em campo ou sem treinamento lança depois. A confiança vem do rastro:
  auditoria de tudo, ⏳ lançamento tardio sinalizado e ⏳ conferência do responsável (o que mudar depois dela
  aparece como "alterado após a conferência").

### Jornada e lacunas (implementado 2026-11-24)
- Jornada esperada: seg–qui **8h27**, sex **7h42**, sábado/domingo 0 (constante em `domain/workday.py`).
- "Meus apontamentos" mostra cada dia útil até hoje: **OK** (igual), **Pendência** (menos), **Verificar** (mais).
  Fim de semana só aparece se tiver horas. ⏳ Feriados e jornada por pessoa.

### Tarefas (implementado 2026-11-24)
- Cadastro do responsável: nome único (2–60), "Conta para a Lei do Bem", ativa. Vêm 9 da planilha antiga:
  Lei do Bem = Desenvolvimento, Documentação, Atualização, Testes e Validações, Reuniões Externas;
  não = Manutenção, Suporte, Correções, Reuniões Internas.

### Estados do período
| Estado      | Quem muda                       | Colaborador edita? |
|-------------|---------------------------------|--------------------|
| `aberto`    | —                               | sim                |
| `enviado`   | colaborador envia               | não (pode recolher se ainda não foi analisado — a confirmar) |
| `devolvido` | gestor/admin devolve com motivo | sim                |
| `aprovado`  | gestor/admin aprova             | não                |
| `fechado`   | admin fecha (ex.: fechamento do mês) | não; só admin reabre, com motivo |

### Permissões
| Ação                                  | colaborador | gestor            | admin |
|---------------------------------------|-------------|-------------------|-------|
| Apontar/editar as próprias horas      | ✔ (período aberto/devolvido) | ✔ | ✔ |
| Ver horas de outros                   | —           | só da equipe      | todos |
| Aprovar/devolver                      | —           | só da equipe      | todos |
| Fechar/reabrir período                | —           | —                 | ✔     |
| Cadastros (usuários, projetos, …)     | —           | — (a confirmar)   | ✔     |
| Relatórios/exportação                 | só os seus  | da equipe         | todos |

### Usuários e acesso (implementado 2026-11-23)
- O **primeiro acesso** (banco vazio) cria o responsável; depois a tela some.
- O responsável cria colaboradores com **senha temporária**; a pessoa é obrigada a trocá-la ao entrar.
- Login sem diferença de maiúsculas; 3–32 caracteres (`a-z 0-9 . _ -`). Senha: 8–128 caracteres, diferente do login.
- **5 senhas erradas seguidas → bloqueio de 15 min** (o responsável desbloqueia ao redefinir a senha).
- Sessão dura 12 h. Trocar a senha encerra as outras sessões; desativar/redefinir encerra todas.
- Sempre existe **pelo menos um responsável ativo**; ninguém tira o próprio acesso de responsável, se desativa ou
  se exclui.
- Colaborador desativado não entra, mas o histórico dele continua.

### Projetos (implementado 2026-11-23)
- Código único (1–20 caracteres, guardado em maiúsculas), nome (2–120), descrição opcional (até 2000).
- Colaborador vê **só projetos ativos** (onde pode apontar); o responsável vê todos.
- "Conta para a Lei do Bem" (padrão sim): desmarcado para o que não é P&D (ex.: tarefas internas).

## Exclusão de dados
Sempre em 2 cliques: link "Excluir" → página com "Confirmar exclusão". Auditada.
| Dado        | Exclusão                                                              | Teste |
|-------------|-----------------------------------------------------------------------|-------|
| Usuário     | Excluir (não a si mesmo; mantém ≥ 1 responsável). Com horas apontadas: só desativar. | `test_delete_user`, `test_cannot_delete_records_with_hours` |
| Projeto     | Excluir. Com horas apontadas: só desativar. | `test_projects_crud_and_visibility`, `test_cannot_delete_records_with_hours` |
| Tarefa      | Excluir. Com horas apontadas: só desativar. | `test_tasks_crud_and_permissions`, `test_cannot_delete_records_with_hours` |
| Apontamento | Excluir (dono ou responsável). ⏳ Só em mês aberto. | `test_only_owner_or_admin_touches_entry` |
| Auditoria   | **Não se exclui** (prova para a Lei do Bem).                          | — |

## Auditoria
Toda criação/edição/exclusão de cadastro, login, senha errada, bloqueio e troca/redefinição de senha registra:
quem, quando (UTC), ação, item e detalhes (na edição, só o que mudou: antes → depois). **Nunca** grava senha.
Somente o responsável consulta (tela Auditoria, últimos 200). Apontamentos (criar/corrigir/excluir, com o colaborador). ⏳ Conferência do mês.
