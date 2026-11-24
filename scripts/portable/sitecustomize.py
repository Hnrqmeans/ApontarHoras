"""Partida do ApontarHoras portátil (copiado para Lib/site-packages pelo scripts/build.ps1).

ApontarHoras.exe é o python.exe oficial renomeado (assinado pela Python Software Foundation). Aberto sem argumentos,
inicia o servidor com a configuração do `ApontarHoras.ini` da mesma pasta. Com argumentos (-c, -m, script), segue o
Python normal. Opções próprias (--porta...) não funcionam aqui: o Python as recusa antes deste arquivo rodar.
Ex.: `ApontarHoras.exe -m apontarhoras.recuperar <login>` (RecuperarAcesso.bat) segue para o módulo.

Sem argumentos, `sys.argv` é `['']` neste ponto. Não basta `len(sys.argv) <= 1`: com `-m módulo` e nada depois,
ele é `['-m']` (o nome do módulo só entra depois) e o servidor subiria no lugar do módulo.
"""

import os
import sys

_exe = os.path.splitext(os.path.basename(sys.executable))[0].lower()
if _exe == "apontarhoras" and sys.argv in ([], [""]):
    from apontarhoras.main import main

    _ini = os.path.join(os.path.dirname(sys.executable), "ApontarHoras.ini")
    sys.exit(main(["--config", _ini]))
