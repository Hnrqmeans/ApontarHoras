# Contribuindo com o ApontarHoras

Obrigado pelo interesse! Este é um projeto de uso interno; contribuições são revisadas pelo mantenedor e **só entram
depois de aprovadas**. Ninguém de fora consegue enviar código direto para as branches do projeto.

## Fluxo
1. Faça um **fork** do repositório.
2. Crie uma branch a partir da **`dev`** (nunca da `main`):
   `git checkout -b feature/minha-mudanca dev` (ou `fix/...`, `docs/...`).
3. Faça as mudanças e garanta que **testes e lint passam**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest
   .\.venv\Scripts\python.exe -m ruff check src tests scripts
   ```
   Mexeu em servidor ou concorrência? Rode também `.\.venv\Scripts\python.exe scripts\carga.py`.
4. Abra um **Pull Request para a `dev`** descrevendo **o que** mudou e **por quê** (o modelo do PR traz o checklist).
5. O CI precisa ficar verde e o mantenedor precisa aprovar. A `main` só recebe a `dev` em versões.

## Regras do projeto
- **Zero dependências no app**: só a biblioteca padrão do Python. PR que adiciona pacote em `dependencies` não entra.
- **Sem dados reais**: o repositório é público. Nada de nomes de pessoas, clientes, e-mails, caminhos pessoais,
  senhas ou planilhas da empresa — nem em testes (use dados fictícios).
- **Permissão no `services`** e **teste de permissão** para toda operação nova; toda regra de cálculo nova com teste.
- Duração em minutos (int); textos de tela e docs em **pt-BR**, identificadores em inglês.
- Migração de banco nova = próximo número livre em `src/apontarhoras/storage/migrations/` (nunca editar uma antiga).
- Commits no formato `tipo(escopo): descrição` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
- Mudou regra de negócio ou estrutura? Atualize `docs/DOMAIN.md` / `docs/ARCHITECTURE.md` no mesmo PR.

Regras completas: [CLAUDE.md](CLAUDE.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Reportar um bug
Abra uma **issue** com:
- versão (rodapé das telas, ex.: `ApontarHoras v0.1.0`) e navegador;
- passo a passo para reproduzir, o que esperava e o que aconteceu;
- o trecho do log do console do servidor no momento do erro.

**Antes de colar**, tire nomes, logins, descrições de atividades e endereços internos. Nunca anexe o arquivo
`apontarhoras.db` nem exportações reais.

## Vulnerabilidade de segurança
**Não abra issue pública.** Fale diretamente com o mantenedor pelo GitHub e descreva o problema; a correção sai
antes da divulgação. O que já está coberto: [docs/SEGURANCA.md](docs/SEGURANCA.md).
