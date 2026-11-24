## O que mudou e por quê
<!-- Descreva a mudança e o motivo. Link para a issue, se houver. -->

## Como testar
<!-- Passos para conferir no navegador, se for mudança de tela. -->

## Checklist
- [ ] A branch saiu da `dev` e o PR é para a `dev`
- [ ] `pytest` passa
- [ ] `ruff check src tests scripts` limpo
- [ ] Nenhuma dependência nova no app (só biblioteca padrão)
- [ ] Nenhum dado real (nomes, clientes, e-mails, caminhos, senhas) no código, testes ou docs
- [ ] Operação nova tem teste de permissão; regra de cálculo nova tem teste
- [ ] Migração nova (se houver) usa o próximo número livre
- [ ] Docs atualizados se mudou regra (`docs/DOMAIN.md`) ou estrutura (`docs/ARCHITECTURE.md`)
