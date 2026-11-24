# Guia do desenvolvedor — build e versões

> **Só para o desenvolvedor.** Nunca escreva aqui senhas ou tokens.
> Será completado na Fase 1 (ambiente) e na Fase 6 (pacote e instalação do servidor).

## Máquina nova (uma vez)
```powershell
cd <pasta do projeto>\ApontarHoras
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"    # app + pytest + ruff (após a Fase 1)
```

## Gerar uma versão
⏳ A definir (base: docs/DESENVOLVEDOR.md do Pagodinho — branch `release/vX.Y.Z`, versão no `pyproject.toml`,
CHANGELOG, merge `--no-ff` em `main` + tag, volta para `dev`).

## Instalar o servidor
⏳ A definir conforme ROADMAP › D1.
