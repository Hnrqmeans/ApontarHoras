# Guia do desenvolvedor — build e versões

> **Só para o desenvolvedor.** Nunca escreva aqui senhas, tokens ou dados reais (o repositório é **público**).

## Máquina nova (uma vez)
```powershell
cd <pasta do projeto>\ApontarHoras
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"    # o app não tem dependências; isto instala só pytest + ruff
```
- Conferir: `.\.venv\Scripts\python.exe -m pytest` e `.\.venv\Scripts\python.exe -m ruff check src tests`.

## Rodar em desenvolvimento
```powershell
.\.venv\Scripts\python.exe -m apontarhoras                    # http://localhost:8080, dados em %LOCALAPPDATA%\ApontarHoras
.\.venv\Scripts\python.exe -m apontarhoras --dados .\dados-dev --porta 8090   # dados separados para testar
```
Banco vazio → a primeira tela cria o responsável. Para recomeçar do zero, apague a pasta de dados de teste.

## Gerar o pacote (máquina limpa)
```powershell
.\scripts\build.ps1          # lint + testes + dist\ApontarHoras\ + dist\ApontarHoras-vX.Y.Z-windows.zip
```
- Baixa uma vez o Python 3.12.10 embeddable oficial (confere SHA-256 e assinatura da PSF) para `build\cache`.
- Conteúdo: `ApontarHoras.exe` (python.exe renomeado), `ApontarHoras.ini`, `LEIA-ME.txt`, o código em
  `Lib\site-packages\apontarhoras`. Nada mais é instalado.
- O `.exe` **não aceita opções** (`--porta`...): o Python embutido as recusa. Tudo vai no `ApontarHoras.ini`.
- Teste rápido do pacote: em `ApontarHoras.ini`, `dados = <pasta de teste>`; dois cliques no .exe.

## Instalar no servidor da empresa
1. Copiar a pasta `ApontarHoras` (do zip) para o servidor, ex.: `C:\ApontarHoras\app`.
2. Em `ApontarHoras.ini`: `rede = sim`, `abrir_navegador = nao`, `dados = D:\ApontarHoras\dados` (pasta com backup).
3. Liberar a porta no firewall **só para a rede interna/VPN**.
4. Iniciar com o Windows: Agendador de Tarefas → "Ao iniciar o computador" → `ApontarHoras.exe` (a combinar com a TI).
5. Abrir `http://<servidor>:8080/` → primeiro acesso cria o responsável.
- **Atualizar**: parar o app, trocar a pasta do app (guardando o `ApontarHoras.ini`), iniciar. Os dados ficam.
  Versão com migração nova atualiza o banco ao abrir; versão antiga recusa abrir banco mais novo.

## Gerar uma versão
Regra: `main` só recebe `dev` **depois do teste manual**. Exemplo para `X.Y.Z`:
1. `git switch -c release/vX.Y.Z` (a partir da `dev`).
2. Versão em `pyproject.toml` e `src/apontarhoras/__init__.py`.
3. `docs/DEVLOG.md` (entrada "Release vX.Y.Z") e `docs/ROADMAP.md` › Status atual.
4. Commit `chore(release): vX.Y.Z`; merge `--no-ff` em `main`; `git tag -a vX.Y.Z`; merge `--no-ff` de volta na `dev`.
5. `.\scripts\build.ps1` na tag → zip sem o sufixo `-dev-`.
