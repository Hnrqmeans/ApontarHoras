@echo off
rem Recupera o acesso de um usuario pelo servidor (ex.: o unico responsavel esqueceu a senha).
rem Roda na pasta do ApontarHoras.exe e usa a pasta de dados do ApontarHoras.ini.
rem Equivale a: ApontarHoras.exe -m apontarhoras.recuperar <login>
setlocal
cd /d "%~dp0"
set "LOGIN="
set /p "LOGIN=Login de quem perdeu o acesso: "
if not defined LOGIN (
    echo Nenhum login informado. Nada foi alterado.
    goto fim
)
"%~dp0ApontarHoras.exe" -m apontarhoras.recuperar "%LOGIN%"
:fim
echo.
pause
endlocal
