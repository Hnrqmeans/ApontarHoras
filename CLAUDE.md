# CLAUDE.md — Guia de início de rotina para IA

> Este arquivo é lido automaticamente no início de cada sessão. Mantenha-o **curto**.
> Detalhes ficam em `docs/` e só devem ser abertos quando a tarefa exigir.

## O projeto em 3 linhas
**ApontarHoras**: app **executável (Windows)** para a equipe apontar horas em projetos de P&D (evidência para a
**Lei do Bem**); no fim do mês um **responsável** confere, fecha e exporta. **Escopo simples por enquanto**
(sem aprovação, sem gestores). Roda no **servidor da empresa** (remotos via VPN); colaboradores usam o navegador.
Stack: **Python 3.12 só com a biblioteca padrão** (`http.server` + `sqlite3` + HTML gerado no servidor) e pacote
portátil com o Python oficial embeddable → abre em **máquina limpa**, sem instalar nada.

## Protocolo de leitura (economia de tokens)
1. Leia **apenas** a seção `## Status atual` de [docs/ROADMAP.md](docs/ROADMAP.md).
2. Leia **apenas a entrada mais recente** de [docs/DEVLOG.md](docs/DEVLOG.md) (topo do arquivo).
3. Abra os demais só se a tarefa tocar no assunto:
   | Tarefa envolve...                                  | Abrir                                        |
   |----------------------------------------------------|----------------------------------------------|
   | Regras de apontamento, aprovação, permissões       | [docs/DOMAIN.md](docs/DOMAIN.md)             |
   | Estrutura de pastas, camadas, servidor, integrações| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
   | Gerar versão, build, máquina nova, instalar servidor| [docs/DESENVOLVEDOR.md](docs/DESENVOLVEDOR.md) (só dev) |
   | Histórico de um bug/decisão antiga                 | buscar no DEVLOG por tag (`grep "#tag"`)     |
4. **Não** varra o repositório inteiro. Use o mapa de módulos em ARCHITECTURE.md e abra só o módulo alvo.

## Protocolo de encerramento (obrigatório ao fim de cada tarefa)
- Adicionar entrada **no topo** de `docs/DEVLOG.md` (modelo no próprio arquivo).
- Marcar/atualizar itens e a seção `Status atual` em `docs/ROADMAP.md`.
- Se mudou regra de negócio → atualizar `docs/DOMAIN.md`. Se mudou estrutura/decisão → `docs/ARCHITECTURE.md`.

## Regras de código (resumo)
- **Zero dependências no app** (pedido do usuário): só biblioteca padrão; `dependencies = []` no pyproject.
  pytest/ruff só no extra `[dev]`. Excel/PDF serão gerados com `zipfile`/XML/texto, sem bibliotecas.
- Camadas: `web → services → storage`; `domain` não importa nada do projeto. Tela **nunca** contém cálculo.
- **Permissão sempre no `services`** (nunca só esconder botão na tela): toda operação recebe o usuário logado
  (`actor`) e confere o papel (`admin` = responsável, `colaborador`) com `require_admin`/`require_user`.
  Teste de permissão para toda operação nova.
- Tempo: duração em **minutos (int)**; nunca `float` de horas. Exibir como `HH:MM` via função única de formatação.
- Datas: `datetime.date`, formato ISO `YYYY-MM-DD` em arquivos/exportações; data-hora em UTC no banco, exibida no
  fuso local.
- Identificadores no código em **inglês**; textos de UI, comentários e docs em **pt-BR**.
- Toda regra de cálculo nova vem com teste em `tests/` (pytest).
- Integrações externas (Excel, e-mail, AD/SSO, ERP) ficam em `integrations/<nome>/` e não são importadas pelo `domain`.
- **Auditoria:** toda criação/edição/exclusão de apontamento, aprovação e cadastro registra quem, quando e o quê
  (mesma transação). Apontamento aprovado/fechado não se edita: só reabrindo (com motivo).
- Senhas: só hash (scrypt/argon2), nunca texto puro nem em log. Nada de segredo no repositório.
- **Todo dado cadastrável precisa de exclusão** (ou desativação, se tiver histórico) com confirmação + teste.
  Exclusão = 2 cliques (link → página "Confirmar exclusão"). Atualizar DOMAIN.md › Exclusão de dados.
- Tela nova = módulo em `web/pages/` com `ROUTES` (acesso `PUBLIC`/`USER`/`ADMIN`) somado em `web/app.ALL_ROUTES`.
  Tela não importa outra tela; peça comum vai para `web/components.py`.
- HTML: todo texto vindo do usuário/banco passa por `components.e()`; formulário POST sempre por `components.form`
  (leva o token anti-CSRF). Sem JavaScript (a CSP bloqueia `script`); cores só por variáveis do `style.css`.
- Tela nova ou fluxo novo → teste em `tests/test_web.py` (servidor real numa porta livre + urllib).
- Configuração do pacote: `ApontarHoras.ini` ao lado do .exe (o Python embutido recusa opções `--` na linha de
  comando). Opção nova → `main.load_settings` + `scripts/portable/ApontarHoras.ini` + teste em `test_main.py`.
- Arquivo novo que não é `.py` (SQL, CSS…) → `[tool.setuptools.package-data]` no `pyproject.toml`.
- Rodar testes: `.venv\Scripts\python.exe -m pytest`. Lint: `.venv\Scripts\python.exe -m ruff check src tests`.

## Fluxo de git
- `main` = só versões estáveis com tag `vX.Y.Z`. **Nunca** commitar direto.
- `dev` = integração. Só recebe branch com **100% dos testes automáticos passando**.
- `main` só recebe `dev` depois do **teste manual do usuário**.
- Trabalho em `feature/<assunto>` / `fix/<assunto>` a partir de `dev`; merge com `--no-ff`.
- Mensagens: `tipo(escopo): descrição` em pt-BR (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
- **Push só quando o usuário pedir.**

## Preferências do usuário
- Usuário compila/executa e avisa se falhar; não é necessário rodar o app após cada edição.
- Commits só quando solicitado.
