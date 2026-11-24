# SEGURANÇA — Para o responsável e para a TI

Como o ApontarHoras protege os apontamentos de horas (evidência para a Lei do Bem), o que ele **não** protege
sozinho e o que a TI precisa configurar no servidor. Os exemplos de pasta e de nome são ilustrativos.

## Resumo em 30 segundos
- Tudo fica num único arquivo, `apontarhoras.db`, na pasta `dados` do `ApontarHoras.ini`. **Quem acessa essa pasta
  lê e altera tudo**: a permissão dela é a principal proteção.
- O app guarda só o *hash* das senhas e das sessões; a auditoria é encadeada e denuncia alteração direta no arquivo.
- Sem HTTPS, a senha atravessa a rede local sem criptografia. Recomendado: HTTPS por um proxy com o certificado da
  empresa.
- Backup diário do arquivo, feito do jeito certo (abaixo). Sem backup, um disco com defeito apaga a evidência.

## Onde ficam os dados
- Arquivo: `apontarhoras.db`, na pasta definida em `dados =` no `ApontarHoras.ini` (ao lado do `ApontarHoras.exe`).
  Vazio = `%LOCALAPPDATA%\ApontarHoras` do usuário que roda o programa — no servidor, **defina uma pasta fixa**
  (ex.: `D:\ApontarHoras\dados`).
- Com o app rodando, aparecem também `apontarhoras.db-wal` e `apontarhoras.db-shm` (modo WAL do SQLite). Fazem
  parte do banco: **não apague** e não copie só o `.db` com o app aberto.
- O console do servidor mostra a pasta em uso ao iniciar (linha "Dados:").

## Backup
Escolha uma das formas:
1. **App parado:** feche o `ApontarHoras.exe` (ou pare a tarefa/serviço) e copie a pasta `dados` inteira.
2. **App rodando (cópia consistente):** use a ferramenta oficial do SQLite, que copia um retrato consistente mesmo
   com gente apontando:
   `sqlite3 D:\ApontarHoras\dados\apontarhoras.db ".backup 'E:\Backup\apontarhoras-AAAA-MM-DD.db'"`
3. **Backup do volume com snapshot (VSS)** do Windows: também serve, porque copia `.db`, `-wal` e `-shm` no mesmo
   instante.

Não sirva: copiar só o `apontarhoras.db` com o app aberto (pode faltar o que ainda está no `-wal`).
Guarde cópias de vários dias/meses (a Lei do Bem pede evidência de anos anteriores) e **teste a restauração** de vez
em quando: copie o backup para uma pasta de teste, aponte um `ApontarHoras.ini` de teste para ela e abra.

## Quem acessa o quê
| Quem | Pelo navegador | Observação |
|------|----------------|------------|
| Colaborador | Só os próprios apontamentos (criar, corrigir, excluir) | Não aponta em nome de outra pessoa. |
| Responsável | Tudo: cadastros, auditoria, corrige/exclui apontamento de qualquer um | Ao mexer no apontamento de outra pessoa, o **motivo é obrigatório** e fica na auditoria. |
| Quem acessa a **pasta do servidor** | — | Lê e altera o arquivo do banco diretamente, sem passar pelo app. |

- A permissão é conferida no servidor em toda operação (esconder um botão não basta; o servidor recusa).
- **Permissão da pasta `dados`:** só a conta que roda o ApontarHoras e os administradores da TI. Ninguém da equipe
  (nem o responsável) precisa acessar a pasta para usar o app.
- **Auditoria encadeada:** cada registro da auditoria leva um selo (SHA-256) calculado a partir do registro
  anterior. Alterar, apagar ou inserir um registro direto no arquivo quebra a corrente, e a tela
  **Auditoria › Verificar integridade** mostra "ALTERAÇÃO DETECTADA a partir do registro #N".
  - Limitação: o código é público e não há segredo. Quem tem acesso ao arquivo pode apagar os últimos registros ou
    recalcular a corrente inteira sem que ela "perceba". Por isso o responsável **anota o número e o selo do último
    registro** (mostrados na mesma tela) de tempos em tempos — por exemplo, no fechamento do mês — e guarda fora do
    servidor. Depois confere ali mesmo ("Conferir o selo do registro nº"): se o registro sumiu ou o selo mudou, houve
    alteração.
  - A corrente detecta; não impede. Impedir é papel da permissão da pasta e do backup.
- **Mês sem trava:** quem estava em campo lança depois. Isso não esconde nada: o apontamento lançado depois do fim
  do mês aparece marcado "Lançado depois do mês", e toda criação, correção e exclusão fica na auditoria.

## Senhas e sessões
- Senhas: guardadas só como hash **scrypt** com sal. Nem o responsável nem a TI conseguem ler a senha de ninguém;
  quem esquece recebe uma senha temporária e troca no próximo acesso.
- 5 senhas erradas seguidas bloqueiam o usuário por 15 minutos (registrado na auditoria).
- Sessões: o navegador recebe um token aleatório (cookie `HttpOnly`, `SameSite=Strict`, 12 h); o banco guarda só o
  SHA-256 dele. Quem ler o arquivo do banco não consegue entrar como outra pessoa.
- Nenhuma senha aparece em log, tela ou auditoria.

## Engenharia reversa
O código do ApontarHoras é público e não contém segredo, senha ou chave. Ler o código ou o pacote não dá acesso a
nada: a segurança depende das senhas de cada pessoa, da permissão da pasta `dados` e da rede.

## Tráfego na rede
- Sem HTTPS, o que o navegador envia (inclusive a **senha no login** e o cookie de sessão) trafega **sem
  criptografia** na rede local. Qualquer equipamento no caminho pode ler.
- A VPN cifra o trecho entre o computador remoto e a empresa, mas **não** o trecho dentro da rede local.
- **Recomendação:** HTTPS com o certificado da empresa por um proxy reverso no servidor (ex.: IIS com URL Rewrite/ARR,
  ou outro proxy que a TI já use), encaminhando para o ApontarHoras em `127.0.0.1:<porta>`. Nesse caso use
  `rede = nao` no `.ini`, para só o proxy alcançar o app. O cookie com `Secure` está previsto
  (`Settings.secure_cookies`).
- O proxy precisa **preservar o cabeçalho `Host`** original (no IIS/ARR: `preserveHostHeader`): o app recusa
  formulário cujo `Origin` não bate com o `Host`, e sem isso todo envio de formulário seria recusado.
- Nunca exponha a porta do ApontarHoras para a internet; acesso de fora só pela VPN.

## Recuperação de acesso (sem a interface web)
Quando não há responsável que consiga entrar (ex.: o único responsável esqueceu a senha ou ficou bloqueado):
1. No servidor, na pasta do `ApontarHoras.exe`, dois cliques em **`RecuperarAcesso.bat`**.
2. Digite o login da pessoa e, duas vezes, uma senha temporária (não aparece na tela).
3. A pessoa entra com essa senha e é obrigada a trocá-la. O usuário é desbloqueado e reativado, e as sessões abertas
   são encerradas.

O mesmo pelo prompt: `ApontarHoras.exe -m apontarhoras.recuperar <login>`. Funciona com o servidor ligado. Fica na
auditoria como "Redefiniu a senha" feito por "servidor (recuperação)". A pasta de dados vem do `ApontarHoras.ini`
da mesma pasta. Só quem tem acesso ao console e à pasta do servidor consegue usar — as mesmas pessoas que já poderiam
alterar o arquivo do banco.

Para não depender disso: **mantenha pelo menos dois responsáveis ativos**. O app avisa no Início e em
Colaboradores quando só há um.

## Porta exclusiva
O ApontarHoras usa a porta do `.ini` com exclusividade: uma segunda cópia aberta na mesma porta **é recusada** ("Não
foi possível usar a porta…"), em vez de dividir as requisições em silêncio. Se aparecer essa mensagem, já existe
uma cópia rodando (ou outro programa usa a porta).

## Checklist para a TI
- [ ] Pasta fixa para os dados (`dados =` no `ApontarHoras.ini`), fora da pasta do programa.
- [ ] Permissão da pasta `dados` só para a conta que roda o ApontarHoras e para a TI.
- [ ] O ApontarHoras inicia sozinho com o servidor (Agendador de Tarefas "ao iniciar" ou serviço), com essa conta.
- [ ] Backup diário consistente (app parado, `sqlite3 .backup` ou snapshot VSS), com retenção de anos e teste de
      restauração.
- [ ] Uma porta interna liberada no firewall, acessível pela rede e pela VPN; **não** exposta à internet.
- [ ] Nome fixo na rede (ou IP fixo).
- [ ] HTTPS com certificado da empresa via proxy reverso (recomendado); com proxy, `rede = nao`.
- [ ] Pelo menos dois responsáveis ativos no app.
- [ ] Quem pode usar o `RecuperarAcesso.bat` (acesso ao console do servidor) está definido.
- [ ] O responsável anota periodicamente o número e o selo do último registro da auditoria (Verificar integridade).
