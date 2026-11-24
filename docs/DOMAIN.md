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

## Exclusão de dados
| Dado        | Exclusão                                                              |
|-------------|-----------------------------------------------------------------------|
| Apontamento | Exclusão com confirmação (só em período aberto/devolvido); auditada.  |
| Usuário, projeto, atividade, cliente | **Desativar** se já tiver apontamentos; excluir só se não tiver. |

## Auditoria
Toda criação/edição/exclusão de apontamento, mudança de estado de período e cadastro registra: usuário, data-hora,
ação, antes/depois. Somente admin consulta.
