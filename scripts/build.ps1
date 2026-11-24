# Gera o pacote portátil do ApontarHoras (Windows): extrair e dar dois cliques em ApontarHoras.exe.
# Funciona em máquina limpa: o Python oficial vai dentro da pasta e o app só usa a biblioteca padrão.
#
# Uso (na raiz do projeto, PowerShell):
#   .\scripts\build.ps1            -> lint + testes + pacote em dist\ApontarHoras\ + zip
#   .\scripts\build.ps1 -SkipTests -> pula lint/testes
#
# Por que não PyInstaller: o .exe gerado não tem assinatura e o Windows 11 (Controle Inteligente de Aplicativos)
# bloqueia. Aqui o ApontarHoras.exe é o python.exe oficial (embeddable) renomeado — a assinatura da Python Software
# Foundation continua válida. O sitecustomize.py do pacote inicia o app (scripts/portable/sitecustomize.py).

param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$python = Join-Path $root ".venv\Scripts\python.exe"

$embedVersion = "3.12.10"
$embedUrl = "https://www.python.org/ftp/python/$embedVersion/python-$embedVersion-embed-amd64.zip"
# SHA-256 do zip acima (o mesmo já conferido e usado no projeto Pagodinho). Trocou a versão? Confira e atualize.
$embedSha256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"

function Invoke-Step([string]$title, [scriptblock]$command) {
    Write-Host "==> $title" -ForegroundColor Cyan
    & $command
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $title (código $LASTEXITCODE)" }
}

function Assert-Signed([string]$file) {
    $signature = Get-AuthenticodeSignature $file
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Python Software Foundation") {
        throw "Assinatura inválida em $file ($($signature.Status)). Apague build\cache e tente de novo."
    }
}

$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
if (-not (git tag --points-at HEAD)) { $version = "$version-dev-$(git rev-parse --short HEAD)" }

if (-not $SkipTests) {
    if (-not (Test-Path $python)) { throw "Ambiente .venv não encontrado (docs/DESENVOLVEDOR.md)." }
    Invoke-Step "Lint" { & $python -m ruff check src tests }
    Invoke-Step "Testes" { & $python -m pytest -q }
}

$cache = Join-Path $root "build\cache"
$embedZip = Join-Path $cache "python-$embedVersion-embed-amd64.zip"
if (-not (Test-Path $embedZip)) {
    Write-Host "==> Baixando o Python oficial $embedVersion (embeddable)" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force $cache | Out-Null
    Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
}
if ((Get-FileHash $embedZip -Algorithm SHA256).Hash.ToLower() -ne $embedSha256) {
    Remove-Item $embedZip
    throw "O Python baixado não confere com o SHA-256 esperado (arquivo apagado do cache). Tente de novo."
}

$output = Join-Path $root "dist\ApontarHoras"
if (Test-Path $output) { Remove-Item $output -Recurse -Force }
Write-Host "==> Montando o pacote v$version" -ForegroundColor Cyan
Expand-Archive $embedZip -DestinationPath $output
Assert-Signed (Join-Path $output "python.exe")
# python.exe (com console): a janela mostra o endereço e fica aberta enquanto o servidor roda
Move-Item (Join-Path $output "python.exe") (Join-Path $output "ApontarHoras.exe")
Remove-Item (Join-Path $output "pythonw.exe")
Assert-Signed (Join-Path $output "ApontarHoras.exe")

# App: só copiar o código (não há bibliotecas de terceiros para instalar)
$sitePackages = Join-Path $output "Lib\site-packages"
New-Item -ItemType Directory -Force $sitePackages | Out-Null
Copy-Item "src\apontarhoras" $sitePackages -Recurse
Get-ChildItem $sitePackages -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Copy-Item "scripts\portable\sitecustomize.py" $sitePackages
Set-Content (Join-Path $output "python312._pth") "python312.zip`r`n.`r`nLib\site-packages`r`nimport site" -Encoding ascii

Copy-Item "scripts\portable\ApontarHoras.ini" $output
Set-Content (Join-Path $output "LEIA-ME.txt") (
    "ApontarHoras v$version`r`n`r`n" +
    "Testar neste computador: dois cliques em ApontarHoras.exe (abre o navegador em http://localhost:8080).`r`n" +
    "No servidor da empresa: em ApontarHoras.ini, rede = sim, abrir_navegador = nao e dados = pasta com backup.`r`n" +
    "Os colaboradores só precisam do navegador: http://<nome-do-servidor>:8080/`r`n`r`n" +
    "Dados (padrão): %LOCALAPPDATA%\ApontarHoras\apontarhoras.db`r`n" +
    "Atualizar = trocar esta pasta, guardando o seu ApontarHoras.ini; os dados continuam onde estão.") -Encoding utf8

$zip = Join-Path $root "dist\ApontarHoras-v$version-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $output -DestinationPath $zip

Write-Host ""
Write-Host "Pronto:" -ForegroundColor Green
Write-Host "  Pasta:      dist\ApontarHoras\ApontarHoras.exe"
Write-Host "  Para levar: $zip"
