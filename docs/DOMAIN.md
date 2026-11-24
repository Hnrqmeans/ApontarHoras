# DOMAIN — Conceitos e regras de apontamento

> Fonte da verdade das regras de negócio. Rascunho de 2026-11-23 — confirmar com o usuário (ROADMAP › D1–D6).

## Contexto: Lei do Bem (2026-11-23)
O app serve para registrar as horas que cada colaborador dedica a **projetos de P&D/inovação**, como evidência para
a Lei do Bem (Lei 11.196/2005). Uso: o colaborador aponta durante o mês; no fim do mês o **responsável** confere,
fecha e exporta. Por isso, cada apontamento precisa de **descrição da atividade** (o que foi feito no projeto) e os
dados de meses fechados não podem mudar sem registro.

**MVP (Fase 1):** papéis só `colaborador` e `responsável` (= admin); estados do mês só `aberto` → `fechado`.
As tabelas abaixo com `gestor`, `enviado`, `devolvido` e `aprovado` são a versão completa, **para depois**.

## Conceitos
| Conceito         | Descrição                                                                                     |
|------------------|-----------------------------------------------------------------------------------------------|
| **Usuário**      | Pessoa que acessa o app: nome, login, e-mail, papel, equipe, jornada esperada, ativo/inativo. |
| **Papel**        | `admin` (tudo), `gestor` (aprova e vê a própria equipe), `colaborador` (só os próprios dados). |
| **Equipe**       | Grupo de usuários com um ou mais gestores.                                                    |
| **Cliente**      | (Opcional) para quem o projeto é feito.                                                       |
| **Projeto**      | Onde as horas são apontadas: código, nome, cliente, ativo, quem pode apontar.                 |
| **Atividade**    | Tipo de trabalho (desenvolvimento, reunião, suporte, deslocamento…); pode ser faturável ou não.|
| **Apontamento**  | Registro de horas: usuário, data, projeto, atividade, duração (min), início/fim opcionais, descrição. |
| **Período**      | Intervalo enviado para aprovação de uma vez (proposta: semana seg–dom).                       |
| **Jornada esperada** | Minutos previstos por dia útil (ex.: 480). Base para "horas faltantes".                   |

## Regras
### Apontamento
- Duração > 0 e ≤ 24h no dia; total do dia acima de um limite configurável gera **aviso** (não bloqueia).
- Se tiver início e fim: duração = fim − início; intervalos do mesmo usuário no mesmo dia **não se sobrepõem**.
- Só em projeto **ativo** e que o usuário pode usar. Projeto desativado mantém os apontamentos antigos.
- Data futura: não permitida (a confirmar).

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

## Exclusão de dados
Sempre em 2 cliques: link "Excluir" → página com "Confirmar exclusão". Auditada.
| Dado        | Exclusão                                                              | Teste |
|-------------|-----------------------------------------------------------------------|-------|
| Usuário     | Excluir (não a si mesmo; mantém ≥ 1 responsável). ⏳ Com horas apontadas: só desativar. | `test_delete_user`, `test_web` |
| Projeto     | Excluir. ⏳ Com horas apontadas: só desativar.                         | `test_projects_crud_and_visibility`, `test_admin_flow_users_and_projects` |
| Apontamento | ⏳ Exclusão com confirmação, só em mês aberto.                         | — |
| Auditoria   | **Não se exclui** (prova para a Lei do Bem).                          | — |

## Auditoria
Toda criação/edição/exclusão de cadastro, login, senha errada, bloqueio e troca/redefinição de senha registra:
quem, quando (UTC), ação, item e detalhes (na edição, só o que mudou: antes → depois). **Nunca** grava senha.
Somente o responsável consulta (tela Auditoria, últimos 200). ⏳ Apontamentos e fechamento do mês.
