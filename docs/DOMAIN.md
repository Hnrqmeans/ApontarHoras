# DOMAIN — Conceitos e regras de apontamento

> Fonte da verdade das regras de negócio. Rascunho de 2026-11-23 — confirmar com o usuário (ROADMAP › D1–D6).

## Contexto: Lei do Bem (2026-11-23)
O app serve para registrar as horas que cada colaborador dedica a **projetos de P&D/inovação**, como evidência para
a Lei do Bem (Lei 11.196/2005). Uso: o colaborador aponta durante o mês; no fim do mês o **responsável** confere,
fecha e exporta. Por isso, cada apontamento precisa de **descrição da atividade** (o que foi feito no projeto) e os
dados de meses já conferidos não podem mudar sem registro.

**MVP (Fase 1):** papéis só `colaborador` e `responsável` (= admin); o mês **não trava** (D9, 2026-11-24): lançar ou corrigir depois da virada do mês é permitido e fica rastreado.
As tabelas abaixo com `gestor`, `enviado`, `devolvido` e `aprovado` são a versão completa, **para depois**.

## Modelo de origem (referência)
As regras vieram do controle em planilha usado antes do app (arquivo fora do git, com dados reais; **nada dele é
copiado para o repositório** — nem dados, nem jornada, nem detalhes internos do arquivo).
- **Campos:** data, pessoa, projeto (`código - cliente - nome`), tarefa (com indicação Lei do Bem), início, término,
  horas e observação.
- **Regras de lançamento:** sem data futura; projeto/tarefa só da lista; horário aceita `7`, `730`, `7:30`;
  término > início; **sem sobreposição** no mesmo dia; período que começa antes das 12:00 e termina depois das
  13:00 **pergunta** se desconta 1 h de almoço; Lei do Bem vem da **tarefa** (projeto que não é P&D = não
  elegível); **observação obrigatória quando conta para a Lei do Bem**.
- **Conferência e relatório:** horas apontadas × jornada esperada por dia → OK / Pendência / Verificar; filtros por
  pessoa, projeto, tipo e período; totais Lei do Bem × não elegível; painel por projeto e tarefa.
- **O que o app acrescenta:** cada pessoa só aponta por si; correção com histórico; auditoria encadeada;
  conferência do mês com selo; acesso simultâneo seguro.

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
| **Conferência**  | Retrato do mês marcado pelo responsável (selo SHA-256). Não trava nada (D9).                  |
| **Jornada esperada** | Minutos previstos por dia da semana, definidos no `ApontarHoras.ini` (`jornada`); padrão 8:00 seg–sex; feriado 0. |
| **Período**      | (Depois) intervalo enviado para aprovação de uma vez — só se o fluxo de aprovação vier.        |

## Regras
### Apontamento (implementado 2026-11-24)
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
- Corrigir ou excluir apontamento de **outra pessoa** (responsável): **motivo obrigatório** (3–500 caracteres),
  gravado na auditoria como "motivo". O dono não precisa.
- **O mês não trava** (D9): quem estava em campo ou sem treinamento lança depois. A confiança vem do rastro:
  - **Lançamento tardio**: criado depois do fim do mês da data trabalhada (data local do lançamento) aparece como
    "Lançado depois do mês" (calculado, sem coluna).
  - **Conferência do responsável**: o que for criado/alterado depois dela aparece como "Alterado após a conferência".

### Jornada e lacunas (implementado 2026-11-24)
- Jornada esperada: configurada no `ApontarHoras.ini` do servidor (`jornada = H:MM` de segunda a domingo); sem
  configuração, **8:00 de segunda a sexta**. A jornada real da empresa fica só no `.ini` do servidor, nunca no git.
- "Meus apontamentos" mostra cada dia útil até hoje: **OK** (igual), **Pendência** (menos), **Verificar** (mais).
  Fim de semana só aparece se tiver horas.
- **Feriados** (cadastro do responsável, tela Feriados): o dia tem jornada 0 e aparece como "Feriado: descrição",
  nunca como pendência. O botão "Adicionar feriados nacionais de AAAA" cadastra 01/01, Sexta-feira Santa (pela
  Páscoa), 21/04, 01/05, 07/09, 12/10, 02/11, 15/11, 20/11 (desde 2024) e 25/12, sem duplicar. Carnaval e Corpus
  Christi são ponto facultativo: o responsável cadastra se a empresa folgar (idem feriados da cidade).
- ⏳ Jornada por pessoa (hoje é a mesma para todos).

### Relatório, conferência e exportação (implementado 2026-11-24, só o responsável)
- **Relatório** (`/relatorio`): filtros — período (padrão = mês atual; máx. 366 dias),
  colaborador, projeto, tipo (Todos / Lei do Bem / Não elegível) e tarefa. Totais: nº de apontamentos, horas, horas
  Lei do Bem e %, não elegíveis. **Painel**: horas por projeto, por tarefa e por colaborador (barras com o número).
- **Pendências da equipe** (`/relatorio/pendencias`): por pessoa ativa, no mês, dias com pendência, dias a verificar
  e horas apontadas × esperadas até hoje (mesma regra de "Meus apontamentos", com feriados).
- **Conferência do mês (D9, sem travar)**: "Marcar mês como conferido" registra quem, quando, nº de apontamentos,
  total e o **selo** (SHA-256 do conteúdo do mês). Depois disso o que mudar aparece como "Alterado após a
  conferência"; se algo mudar (inclusive exclusão), o mês avisa "mudou desde a conferência". Pode conferir de novo
  (vale a última). Nada é bloqueado.
- **Exportação**: Excel (.xlsx, abas "Apontamentos" e "Resumo") e Impressão/PDF (navegador › Imprimir › Salvar como
  PDF), com o **selo de conferência** = SHA-256 dos filtros + linhas exportadas (igual nos dois formatos). Texto que
  começa com `= + - @` recebe `'` no Excel (sem fórmula injetada). Toda exportação fica na auditoria.

### Tarefas (implementado 2026-11-24)
- Cadastro do responsável: nome único (2–60), "Conta para a Lei do Bem", ativa. Vêm 9 tarefas padrão (editáveis):
  Lei do Bem = Desenvolvimento, Documentação, Atualização, Testes e Validações, Reuniões Externas;
  não = Manutenção, Suporte, Correções, Reuniões Internas.

### Situação do mês (implementado — D9: o mês nunca trava)
| Situação | Como fica | Colaborador edita? |
|---|---|---|
| Sem conferência | Normal | sim |
| Conferido | Selo do mês guardado; quem/quando | sim — o que mudar aparece como "alterado após a conferência" |
| Mudou desde a conferência | Aviso no relatório; conferir de novo vale a última | sim |

(Depois, só se vier fluxo de aprovação: `enviado` / `devolvido` / `aprovado` por gestor.)

### Permissões
| Ação                                  | colaborador | gestor            | admin |
|---------------------------------------|-------------|-------------------|-------|
| Apontar/editar as próprias horas      | ✔ (sempre; mês não trava) | (depois) | ✔ |
| Corrigir/excluir horas de outra pessoa | —          | (depois)          | ✔ com motivo |
| Ver horas de outros / relatório        | só as suas (Meus apontamentos) | (depois) | todos |
| Conferir o mês, exportar Excel/PDF     | —          | —                 | ✔     |
| Cadastros (usuários, projetos, tarefas, feriados) | — | —           | ✔     |
| Auditoria e Verificar integridade      | —          | —                 | ✔     |

Hoje só existem `colaborador` e `responsável` (admin); a coluna gestor é para depois.

### Usuários e acesso (implementado 2026-11-23)
- O **primeiro acesso** (banco vazio) cria o responsável; depois a tela some.
- O responsável cria colaboradores com **senha temporária**; a pessoa é obrigada a trocá-la ao entrar.
- Login sem diferença de maiúsculas; 3–32 caracteres (`a-z 0-9 . _ -`). Senha: 8–128 caracteres, diferente do login.
- **5 senhas erradas seguidas → bloqueio de 15 min** (o responsável desbloqueia ao redefinir a senha).
- Sessão dura 12 h. Trocar a senha encerra as outras sessões; desativar/redefinir encerra todas.
- Sempre existe **pelo menos um responsável ativo**; ninguém tira o próprio acesso de responsável, se desativa ou
  se exclui.
- Colaborador desativado não entra, mas o histórico dele continua.
- **Recuperação pelo servidor** (`RecuperarAcesso.bat` ou `ApontarHoras.exe -m apontarhoras.recuperar <login>`):
  define senha temporária, desbloqueia, reativa, encerra sessões e obriga a troca. Auditado como "Redefiniu a
  senha" por "servidor (recuperação)". Quem tem o console do servidor já tem o arquivo do banco.
- Com um só responsável ativo, Início e Colaboradores avisam: "Cadastre um segundo responsável".

### Projetos (implementado 2026-11-23)
- Código único (1–20 caracteres, guardado em maiúsculas), nome (2–120), descrição opcional (até 2000).
- Colaborador vê **só projetos ativos** (onde pode apontar); o responsável vê todos.
- "Conta para a Lei do Bem" (padrão sim): desmarcado para o que não é P&D (ex.: tarefas internas).
- **Importar lista** (responsável): colar uma linha por projeto, `CÓDIGO - Cliente - Nome` ou `CÓDIGO - Nome` (TAB do
  Excel também vale). Pré-visualiza (nova / já existe → ignorada / inválida com motivo; repetida = inválida) e
  importa só as novas numa transação, auditando cada projeto. Até 500 linhas.

## Exclusão de dados
Sempre em 2 cliques: link "Excluir" → página com "Confirmar exclusão". Auditada.
| Dado        | Exclusão                                                              | Teste |
|-------------|-----------------------------------------------------------------------|-------|
| Usuário     | Excluir (não a si mesmo; mantém ≥ 1 responsável). Com horas apontadas: só desativar. | `test_delete_user`, `test_cannot_delete_records_with_hours` |
| Projeto     | Excluir. Com horas apontadas: só desativar. | `test_projects_crud_and_visibility`, `test_cannot_delete_records_with_hours` |
| Tarefa      | Excluir. Com horas apontadas: só desativar. | `test_tasks_crud_and_permissions`, `test_cannot_delete_records_with_hours` |
| Apontamento | Excluir (dono, ou responsável com motivo). O mês não trava (D9). | `test_only_owner_or_admin_touches_entry`, `test_confianca` |
| Feriado     | Excluir (o dia volta a ter jornada). | `test_holidays_crud_and_audit` |
| Auditoria   | **Não se exclui** (prova para a Lei do Bem).                          | — |

## Auditoria
Toda criação/edição/exclusão de cadastro, login, senha errada, bloqueio e troca/redefinição de senha registra:
quem, quando (UTC), ação, item e detalhes (na edição, só o que mudou: antes → depois). **Nunca** grava senha.
Somente o responsável consulta (tela Auditoria, últimos 200). Também: apontamentos (criar/corrigir/excluir, com o
colaborador e o motivo), tarefas, feriados, importação, conferência do mês e exportações (com o selo).
- **Auditoria encadeada** (à prova de alteração): cada registro tem `hash = SHA-256(hash anterior + conteúdo)`.
  Auditoria › **Verificar integridade** mostra "Íntegro: N registros" ou "ALTERAÇÃO DETECTADA a partir do #X".
- Limite: apagar os últimos registros ou recalcular a corrente inteira não se detecta sozinho — por isso a tela mostra
  o nº e o selo do último registro para o responsável **anotar fora do servidor** e comparar depois.
