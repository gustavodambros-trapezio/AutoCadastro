# AutoCadastro Protheus — contexto do projeto

Automação que cria usuários no **TOTVS Protheus** (WebApp) a partir de um site
local. Substituiu uma automação anterior feita "na mão" por um agente que
clicava por posição na tela.

**Estado (30/07/2026, ~13h): instalado e rodando no PC da sala de servidores.
O lote real da filial 01ALFA0001 está COMPLETO — 14/14 criados** (execuções
10-12; a 12 rodou limpa, 7 criados + 7 pulados, 0 erros, ~3 min/usuário, com
todos os fixes do dia validados: wizard Finalizar-primeiro, espera real
pós-Confirmar, ID obrigatório, status 1 a 1 no site, botão Parar).
A frente nova de **VENDEDOR** está com a infra paralela pronta (ver seção
própria), travada só na 2ª sessão do Protheus que não termina de carregar.
Em 29/07/2026 o fluxo completo foi validado com três criações reais:

| Nome | Login | Grupo | Cód. caixa | ID | Filial |
|---|---|---|---|---|---|
| BRENDA RAMOS PINHEIRO | BRENDA.PINHEIRO | 000012 | CZY | 001288 | 01DOMA0001 |
| CAUA GOSTEINSKI | CAUA.GOSTEINSKI | 000012 | CZZ | 001289 | 01DOMA0001 |
| DAIANE DOS SANTOS MORAES | DAIANE.MORAES | 000013 | D00 | 001290 | 01DOMA0001 |

---

## Arquitetura (3 camadas)

```
site/app_autocadastro.py    site Flask (porta 8025) — grade estilo planilha
        │                   (NOME|CPF|FUNÇÃO, cola do Excel), histórico,
        │                   planilha, exportar Excel, banco SQLite
        │  subprocess (--json-b64)
        ▼
robo/protheus_criar_usuario.py   orquestra o lote: agrupa por filial, escolhe
        │                         login, decide grupo, devolve JSON no stdout
        ▼
robo/protheus_ui.py         camada de tela: sabe operar o Protheus
                            (seletores reais, tratamento de popups)
```

**Estrutura de pastas (reorganizada em 30/07/2026):**

```
AutoCadastro/
├── site/    app_autocadastro.py
├── robo/    protheus_criar_usuario.py, protheus_ui.py, atualizar_filiais.py
├── docs/    SELETORES_CAPTURADOS.md, SETUP_SERVIDOR.md, TRANSFERIR_PARA_SERVIDOR.md
└── raiz:    .env, protheus_config.json, filiais.json, autocadastro.db,
             CLAUDE.md, README.md   ← dados/configs ficam na RAIZ
```

Nos três .py, `BASE_DIR` aponta para a **raiz** do projeto
(`dirname(dirname(__file__))`) — db, `.env`, configs e `filiais.json` são
resolvidos a partir dela.

O site nunca fala com o Protheus direto; o robô nunca sabe de planilha/banco.

## Como o robô alcança o Protheus

Modo **`attach`** (padrão, e é o que o usuário quer): conecta a um Chrome que
**já está aberto e logado** no Protheus, iniciado com
`--remote-debugging-port=9222 --user-data-dir=C:\ChromeProtheus`.
O site verifica a porta e desabilita o botão de criar se não houver sessão.

**Credenciais (decisão revista em 30/07/2026):** existe um `.env` na pasta com
o usuário de robô do Protheus (`LOGIN_BOT_PROTHEUS`/`SENHA_BOT_PROTHEUS` =
`AUTO.PROTHEUS`) e o login do site (`LOGIN_SITE_FRONT`/`SENHA_SITE_FRONT`).
**O robô agora reloga sozinho**: `garantir_sessao()` detecta a tela de login,
autentica com o `.env` e entra no módulo (login PO-UI → seleção de contexto
com a filial `01DOMA0001` só para entrar → `esperar_modulo_pronto`); o lote
troca para a filial certa depois, via `trocar_modulo()`. A filial de entrada
é configurável (`PROTHEUS_FILIAL_INICIAL` / `filial_inicial` no config).

Existe o modo `launch` (o robô loga sozinho com usuário/senha do config), mas
não use sem o usuário pedir.

## Frente nova: criar VENDEDOR a partir do usuário (iniciada 30/07/2026)

Decisões do usuário:
- Desenvolver **sem tocar no código de produção** (usuários). O robô novo é
  `robo/protheus_criar_vendedor.py`, que reusa `protheus_ui.py` por HERANÇA
  (`TelaVendedor(TelaProtheus)`) e importa o módulo de usuários para
  attach/login/trava — nada dos arquivos de produção muda.
- **Rodar em paralelo de verdade**: o Protheus aceita duas sessões do mesmo
  login (confirmado pelo usuário). O robô de vendedor usa um SEGUNDO Chrome
  (porta **9223**, perfil `C:\ChromeProtheus2` — variáveis
  `PROTHEUS_CHROME_DEBUG`/`PROTHEUS_CHROME_USER_DATA` definidas no próprio
  script) e a **trava agora leva a porta no nome**
  (`protheus_autocadastro_9222.lock` / `_9223.lock`) — instâncias diferentes
  não se bloqueiam; dois robôs no MESMO Chrome continuam se serializando.
  No futuro, o site pode ganhar a frente de vendedor ou subir um 2º site
  (`$env:AUTOCADASTRO_PORTA='8026'`).
- Teste de sessão: `python robo\protheus_criar_vendedor.py --so-sessao`.
- A permissão do protocolo **web-agent:** foi copiada do perfil de produção
  para o `C:\ChromeProtheus2` editando `Default\Preferences`
  (`protocol_handler.allowed_origin_protocol_pairs`) — funcionou, o perfil
  novo não pede mais o diálogo do WebAgent.
- **DESCOBERTA-CHAVE (31/07): 2ª sessão funciona em ABA do MESMO Chrome, não
  em Chrome separado.** Num 2º Chrome (perfil próprio) a sessão trava para
  sempre no overlay "Dicionário de parametros / Carregando" (>15 min, refresh
  não resolve — limitação aparente do WebAgent local, que atende UM
  navegador). Já numa **aba nova do Chrome de produção** (`testa_aba2.py` no
  scratchpad): login AUTO.PROTHEUS + contexto + módulo carregado **em 68s**,
  sem afetar a aba 1. As "5 telas" que o usuário abre são abas/janelas do
  mesmo navegador. → O plano multi-telas deve usar N ABAS do Chrome 9222,
  um robô por aba. O Chrome 2 (9223/`C:\ChromeProtheus2`) fica abandonado
  como abordagem para MESMO login (ainda pode servir com um 2º login de robô).
- **Capacidade da máquina (medida 31/07)**: i3-12100 (4c/8t, sobra CPU),
  **7,8 GB de RAM com só 1,8–2,4 GB livres** — RAM é o limitador. Chrome com
  1 aba Protheus ≈ 0,9 GB; cada aba extra ≈ 0,3 GB + ~0,15 GB por robô
  (python+chromedriver). Estimativa segura com a RAM atual: **3 telas
  simultâneas** (4 no talo). Para as 5 telas do plano do usuário →
  **upgrade para 16 GB** recomendado.
- **O que falta ENGENHEIRAR para N robôs em abas** (não começado):
  (a) cada robô criar/adotar a própria aba e nunca tocar nas outras — hoje
  `_focar_aba_protheus` pega a PRIMEIRA aba do Protheus; (b) trava por aba
  (hoje é por porta); (c) o site gerenciar N execuções simultâneas e dividir
  um lote entre telas (hoje `_trava_execucao`/`_proc_atual` assumem 1);
  (d) validar clique/tecla em ABA EM SEGUNDO PLANO (CDP entrega eventos a
  aba sem foco, mas o Chrome estrangula timers de aba de fundo — testar com
  criação real; talvez `--disable-background-timer-throttling`).
- FALTA: mapear a tela de Cadastro de Vendedores (rotina no menu, campos,
  regras — perguntar ao usuário) e implementar preencher/confirmar com a
  regra de testes = preencher e DESCARTAR até autorização.

## Regras de negócio (confirmadas pelo usuário)

- **Login:** `PRIMEIRO.ULTIMO`; se existir, `PRIMEIRO.PENULTIMO`,
  `PRIMEIRO.ANTEPENULTIMO`… e, esgotados os nomes, `PRIMEIRO.ULTIMO2`, `3`, `4`…
  Conectores (DA/DE/DO/DAS/DOS) nunca entram como sobrenome. Sem acentos.
- **Exceção SMART POS (regra do usuário, 31/07/2026):** nome que começa com
  número e contém SMART (ex.: `01 SMART POS LV 023`) → tudo igual, só o
  login muda e é FIXO: `SMARTPOS(nº do início).(código da filial)` — ex.:
  `SMARTPOS01.01LVER0023`. Sem cascata: se já existir, dá erro (apurar).
  Implementado em `login_smart()` (`protheus_criar_usuario.py`), testado com
  7 casos incluindo "SMARTPOS" junto e nomes normais (não disparam).
- **Senha:** `Grupo@2026`, e **desmarcar** "Forçar troca de senha no próx. logon".
- **Regra de acesso por grupo:** `1 - Priorizar`. Na grade de Grupos, **Prioriza = Sim**.
- **Grupo:** função contendo `GERENTE` **ou** `LIDER DE LOJA` → **000013**
  (GRUPO GERENTES DE UNIDADE). Todas as outras (CAIXA, FRENTISTA, LIDER DE
  PISTA, LUBRIFICADOR…) → **000012** (GRUPO PARA CAIXAS DO PDV).
- **E-mail:** nunca preencher.
- **Contexto:** Grupo `01` fixo, **Ambiente `12`** (Controle de Lojas) — o
  padrão vem `1`, sempre trocar.
- **Filial:** sempre pelo **CÓDIGO** (`01DOMA0001`), nunca pelo nome — 45 das 67
  filiais têm nome repetido (26 "POSTO LINHA VERDE", 19 "AUTO POSTO ALMIRANTE").
  É também assim que o usuário nomeia as páginas/abas dele.
- Protheus gera o **código do caixa** (3 caracteres) e o **ID** (6 dígitos);
  os dois são gravados no banco do site.
- **O ID (6 dígitos) é OBRIGATÓRIO e é a confirmação de que o usuário foi
  criado** (regra do usuário, 30/07/2026). Se o robô não conseguir ler o ID
  na lista, NÃO marca CRIADO e **interrompe o lote inteiro**
  (`SemConfirmacaoID`) — nunca passa ao próximo usuário sem essa confirmação.
- A tela **"Usuários criados pela automação"** (ex-"Planilha") mostra **só
  STATUS=CRIADO** — cadastros que falharam aparecem apenas no Histórico. O
  Exportar Excel fica dentro dela (e também exporta só os criados). Pedidos
  do usuário em 30/07/2026.
- Nessa tela há um ✕ por linha que apaga o registro
  **somente do banco local** (o Protheus não é tocado) — serve para liberar a
  trava de CPF repetido e recadastrar. Pedido do usuário em 30/07/2026.

## ⚠️ Armadilhas do TOTVS WebApp (todas já custaram bug)

O detalhe técnico completo está em [SELETORES_CAPTURADOS.md](docs/SELETORES_CAPTURADOS.md).
Resumo do que **não** funciona:

1. **Duas tecnologias na mesma página.** Login/contexto = Angular PO-UI dentro
   de um **iframe** (`src` contém `app-root`). Módulo/cadastro = SmartClient com
   web components `wa-*` em **shadow DOM** e ids voláteis `COMPxxxx` — localizar
   por `data-advpl`, `caption` ou texto+coordenada, **nunca por id**.
2. **Clique sintético não funciona** em checkbox, botões de wizard, células de
   grade e **troca de sub-aba**. Só **clique real** (`ActionChains`). Sintoma
   traiçoeiro: não dá erro, só não acontece nada (a sub-aba 'Grupos' parecia
   clicada e a ativa continuava 'Superior', com o cabeçalho 'Grupo' em width=0).
3. **Nunca mexer na propriedade `checked` por JS** — dessincroniza host e
   renderização. O `<input>` do shadow DOM é só desenho: seu `.checked` **nunca
   muda** e `send_keys` nele não escreve nada. Estado real = host `wa-checkbox`.
4. **Foco não vai para o campo clicando.** Depois do `Incluir` o foco fica no
   BOTÃO, e clicar no campo pode focar o **vizinho** (um login foi digitado em
   'Nome completo' perdendo o 1º caractere). Use `focar_campo()`, que anda com
   TAB **conferindo** que `active_element` é o host do campo alvo.
5. **Limpar campo:** rajada de BACKSPACE em campo **vazio** joga o foco para o
   campo anterior; `setSelectionRange` não dá erro mas **não substitui nada**.
   Apagar exatamente `len(valor_atual)` caracteres.
6. **Popups precisam ser fechados pelo botão DE DENTRO deles** — um
   `clica_caption('Fechar')` global acerta o botão do formulário e o popup
   nunca sai. E ao procurar o popup por texto, pegar o `wa-dialog` de **menor
   área** (a janela toda também "contém" o texto).
7. **`textContent` não atravessa shadow DOM** — descer nos `shadowRoot` à mão.
8. **Modal "Há alterações não salvas no formulário!"** (Continuar editando /
   Salvar / **Sair da página**) aparece ao fechar formulário sujo e **bloqueia a
   tela inteira**. Use `abandonar_formulario()`, que responde "Sair da página".
   **NUNCA clicar em "Salvar" ali** — gravaria um cadastro pela metade.
9. **Não filtrar por coordenada fixa**: o formulário **rola** conforme os campos
   recebem foco. Posicione-se em relação a um elemento encontrado (ex.: o
   cabeçalho da grade), não em `y > 490`.
10. **`Trocar módulo` não existe no DOM enquanto uma rotina está aberta** →
    `fechar_rotina()` antes de trocar de filial (fecha a aba e responde **Sim**
    a "O processo da sessao atual sera interrompido").
11. **Ao abrir a rotina o Protheus pode pedir o contexto de novo** — é só
    confirmar; os valores já estão certos.
12. **Nunca detectar o diálogo de contexto pelo texto "TOTVS Linha Protheus"**:
    a tela de carregamento diz "Aguarde para utilizar o TOTVS Linha Protheus"
    e dá falso positivo. Use `no_dialogo_contexto()`.
13. **Na janela de contexto opere o HOST** `wa-text-input` (no formulário de
    usuário é o oposto: digita-se no campo focado). E **confira o que ficou
    gravado** antes de confirmar — casar label→campo por coordenada ali é
    frágil (o label 'Ambiente*' chegou a alinhar com o campo do Grupo).
14. **`usuario_existe()` NÃO serve como checagem prévia de login**: depois de
    criar alguém o browse fica posicionado só naquele registro, e o campo
    Pesquisar da rotina filtra por outra coluna. A cascata de logins é
    **reativa**: o Protheus avisa "Não é permitido duplicação de códigos" **ao
    sair do campo Usuário**, e `define_login()` troca de candidato ali.
15. **Headless não funciona.** O WebApp exige o **TOTVS WebAgent** (protocolo
    `web-agent:`), que o Chrome headless não abre. Janela visível, sempre.
16. **Wizard "Configuração do caixa"**: os botões vêm com texto fragmentado
    pelo accesskey (`"vançar >> A"`, `"inalizar F"`) → comparar por trecho
    **parcial**.
17. **Tela "Tem certeza que deseja excluir o item abaixo?"** é a rotina de
    Excluir do cadastro. Se o robô topar com ela (ex.: sobra de uma ação
    manual na mesma sessão do Chrome), **Fechar — nunca Confirmar**. Em
    30/07/2026 ela apareceu após a execução nº 9; era o próprio usuário
    excluindo ALEXSANDRO.SANTOS manualmente para recadastrar depois.
18. **Popup "Autorização do superior"** (Login do usuário / Senha atual,
    botões Cancelar/Finalizar) pode aparecer ao abrir a rotina e **bloqueia a
    tela** — derrubou um lote inteiro de 14 na filial 01ALFA0001 em 30/07/2026
    ("Tela 'Cadastro de usuários' não abriu"). Tratamento definido pelo
    usuário: clicar **Cancelar** (botão de dentro do popup), esperar carregar
    e continuar. Nunca `Finalizar`. Está em `cancela_autorizacao_superior()`,
    chamado por `fecha_dialogos()`.

## Caminho na tela (validado)

```
login → contexto (Grupo 01 / Filial <código> / Ambiente 12) → Confirmar
     → Miscelanea (18) → Usuários  → "Cadastro de usuários"
     → Incluir → login (cascata) → Nome/Senha/Confirme
     → desmarcar "Forçar troca de senha" → combo "1 - Priorizar"
     → sub-aba Grupos: código + Prioriza=Sim
     → Confirmar → popup "Codigo do Novo Usuario: XXX"
     → wizard "Configuração do caixa" (Avançar >> … Finalizar)
     → "Registro inserido com sucesso." → lê o ID na lista
```

## Segurança / cuidados ao trabalhar aqui

- **Criar usuário é irreversível na prática.** Só criar com autorização
  explícita do usuário, e nome por nome. Para testar mecânica, preencha o
  formulário e **descarte** com `abandonar_formulario()`.
- Ao mexer em `atualizar_filiais.py` ou no diálogo de contexto: só **ler** e
  **Cancelar** no fim, para não alterar o contexto da sessão do usuário.
- Se algo der errado no meio, **não afirme o que não sabe** (ex.: não marcar
  filial como "não encontrada" sem ter certeza de que a escrita funcionou).
- O site é aberto na rede com autenticação básica simples
  (`admin` / senha no `protheus_config.json`).

## Comandos úteis

```powershell
# subir o site (rodar da raiz do projeto)
python site\app_autocadastro.py       # http://<ip>:8025

# criar 1 usuário direto pelo robô (teste)
python robo\protheus_criar_usuario.py --nome "TESTE DA SILVA" --cpf 000 --funcao CAIXA --filial 01ALFA0001

# completar/atualizar descrições de filiais (só lê o Protheus)
python robo\atualizar_filiais.py
python robo\atualizar_filiais.py --codigos 01NOVO0001

# testar em outra porta de depuração sem editar o config
$env:PROTHEUS_CHROME_DEBUG='127.0.0.1:9223'
```

## Instalação no servidor — o que foi feito em 30/07/2026

Sessão de instalação/evolução no PC da sala de servidores (Windows 11 Pro,
usuário `ADMIN`). Tudo abaixo está **feito e testado**:

1. **Dependências**: Python 3.14.5 + selenium/flask/waitress/openpyxl.
   ⚠️ Nesta máquina o comando `pip` NÃO está no PATH — use `python -m pip`.
2. **Atalho** "Chrome Protheus (robo)" na área de trabalho, com
   `--remote-debugging-port=9222 --user-data-dir=C:\ChromeProtheus`
   **`--no-first-run --no-default-browser-check`** — as duas flags extras são
   necessárias: sem elas o perfil novo trava na tela "Faça login no Chrome"
   (`chrome://intro`) e o Protheus nem abre.
3. **Chrome do robô no ar** (porta 9222), **logado como `AUTO.PROTHEUS`**
   (credencial do `.env`) no Ambiente 12, filial 01DOMA0001.
4. **Site no ar** em `http://10.15.17.231:8025`. Regra de firewall da porta
   8025 criada pelo usuário (exige admin). ⚠️ O site está rodando como
   processo manual — a tarefa agendada da Parte 5 do SETUP_SERVIDOR.md
   (subir com o Windows) ainda NÃO foi criada.
5. **Teste de ponta a ponta sem criar ninguém**: CLI com filial falsa
   `01ZZZZ9999` → status de filial inexistente ✅ (login, attach, contexto e
   saída JSON todos exercitados). O status na época era `AGUARDANDO FILIAL`;
   foi renomeado para `ERRO: FILIAL NÃO EXISTE NO PROTHEUS` a pedido do
   usuário (conta como erro e fica vermelho).

### Mudanças de código desta sessão (30/07/2026)

- **Formulário virou grade estilo planilha** (`app_autocadastro.py`): tabela
  com colunas fixas # | NOME | CPF | FUNÇÃO | ✕ no lugar do textarea. Colar
  do Excel espalha pelas células a partir da célula focada (TAB ou `;`),
  criando linhas conforme precisa; Enter desce; última linha em branco vira
  nova sozinha; linha incompleta bloqueia o envio com alerta. No submit, o
  JS serializa tudo no formato antigo `NOME;CPF;FUNÇÃO` no campo oculto
  `#linhas` — **o backend (`parse_linhas`, rota `/criar`) não mudou**.
  Testado com Selenium numa aba nova do Chrome do robô: 10/10 verificações.
- **Auto-login do robô** (`protheus_criar_usuario.py`): ver seção
  "Como o robô alcança o Protheus".
- **✕ de apagar na Planilha** (`app_autocadastro.py`, rota POST
  `/apagar_usuario/<id>`): apaga só do banco local, com confirm() explicando.
  Testado com registro descartável; os 3 usuários reais ficaram intactos.
- **Popup "Autorização do superior"** (`protheus_ui.py`,
  `cancela_autorizacao_superior()` + `fecha_dialogos()`): cancela o popup que
  derrubou o lote de 14 da 01ALFA0001 (armadilha 17). O popup já tinha sido
  fechado manualmente quando o fix ficou pronto, então o teste ao vivo não
  rodou contra ele — a detecção (`tem_texto`) e o clique escopado
  (`JS_CLICA_NO_DIALOGO`, mesmo mecanismo do modal "Sair da página") são
  caminhos já validados.
- **Tela "Planilha" → "Usuários criados pela automação"**
  (`app_autocadastro.py`): mostra e exporta **só STATUS=CRIADO**; o botão
  Exportar Excel saiu do menu do topo e entrou na página. Falhas ficam só no
  Histórico.
- **Status de filial inexistente renomeado** (`protheus_criar_usuario.py`,
  constante `STATUS_FILIAL_INEXISTENTE`): `AGUARDANDO FILIAL` →
  `ERRO: FILIAL NÃO EXISTE NO PROTHEUS`. Os 14 registros antigos da execução
  nº 7 foram migrados no banco e os contadores de erros recalculados
  (execuções 7 e 8 agora mostram 14 erros cada).
- **Wizard do caixa sem esperas fixas** (`protheus_ui.py`,
  `percorrer_wizard_caixa`): no lugar dos `sleep(4)`/`sleep(7)` por etapa
  (~35-40s por usuário só de espera), agora clica Avançar e espera o **texto
  do diálogo do topo mudar** (`_espera_dialogo_mudar`, checagem a cada 0.3s,
  teto de 6s/10s — no pior caso equivale ao comportamento antigo). Todas as
  etapas do wizard são só Avançar + Finalizar no fim (confirmado pelo
  usuário). ⚠️ Entrou DEPOIS da execução nº 9 começar — vale a partir da
  execução seguinte; ainda não foi visto rodando ao vivo.
- **Botão "■ Parar execução"** (`app_autocadastro.py`): aparece na tela da
  execução enquanto está RODANDO. Rota POST `/parar_execucao/<id>` mata o
  processo do robô com `taskkill /T /F` (derruba o chromedriver junto; o
  Chrome do Protheus não é filho e fica de pé). `rodar_execucao` passou de
  `subprocess.run` para `Popen`+`communicate` com o handle em `_proc_atual`.
  Quem já foi criado fica CRIADO; os PROCESSANDO viram "ERRO: execução parada
  pelo usuário no site" e a execução fica com status **PARADA** (vermelho no
  histórico). Ainda não testado ao vivo.
- **Robô abre o Chrome sozinho** (`protheus_criar_usuario.py`,
  `_abrir_chrome_robo()`): no modo attach, se a porta 9222 não responde, o
  robô abre o Chrome com os mesmos parâmetros do atalho (perfil
  `C:\ChromeProtheus`, configurável via `chrome_user_data`/`chrome_exe`) e o
  `garantir_sessao()` loga. O site não bloqueia mais criação com Chrome
  fechado (banner virou aviso informativo, botão sempre habilitado, checagem
  removida da rota `/criar`).
- **`garantir_sessao()` espera a página se definir**: logo após abrir o
  Chrome, `esta_no_login()` devolvia False durante o carregamento e o robô
  achava a sessão ok (falhou com "Botão 'Trocar módulo' não encontrado").
  Agora espera até afirmar em que tela está (login / seleção / módulo, teto
  90s). Validado: abriu, logou como AUTO.PROTHEUS e entrou no módulo sozinho.
- **Histórico: FALHOU com ≥1 erro e CANCELADO no botão de parar** (pedido do
  usuário): `_finalizar` rebaixa CONCLUIDA→FALHOU se houver erro; parada
  manual grava CANCELADO. Execuções antigas 7/8 migradas para FALHOU.
- **Parar execução limpa a trava**: o robô morto deixava
  `%TEMP%\protheus_autocadastro.lock` para trás e a execução seguinte
  esperava até 15 min ("Outra execução em andamento..."). A rota
  `/parar_execucao` agora remove o lock após o taskkill.
- **INCIDENTE da execução nº 9 (30/07, 10:28–10:42, 01ALFA0001, 14 pessoas)**:
  a partir do 2º usuário o robô degradou com erros em série ("formulário
  ainda aberto", "não consegui pôr o foco no campo 'Usuário'") e foi morto
  via taskkill a pedido do usuário. Saldo confirmado pelo usuário: **só
  ALEXSANDRO.SANTOS foi criado (código D06), e ele mesmo o excluiu
  manualmente** — ninguém do lote existe no Protheus, o banco do site
  (14×ERRO) está correto e o lote pode ser recadastrado direto. Causa raiz do
  travamento não identificada — observar a próxima execução. Obs.: durante o
  lote a tela da execução mostra todos como PROCESSANDO até o fim (o robô só
  devolve o JSON no final) — por isso pareceu "parado no 1º usuário".
- **Armadilha 14 reconfirmada (30/07)**: pesquisar login ou nome no campo
  Pesquisar da rotina devolve nada mesmo para usuário que existe
  (BRENDA.PINHEIRO) — não usar como verificação de existência.
- **⚠️ POST-MORTEM execução nº 10 (30/07, 11:08–11:40, 01ALFA0001) — CAUSA
  RAIZ dos 4-5 min/usuário e dos travamentos (execuções 9 e 10):** na última
  etapa do wizard do caixa os botões "Finalizar" E "Avançar >>" ficam ambos
  visíveis (o Avançar desabilitado, mas com tamanho > 0). O loop do wizard
  testava Avançar PRIMEIRO com `continue` — clicava no botão morto, esperava,
  e repetia 25×, nunca chegando ao Finalizar (~3-4 min queimados POR
  usuário). Pior: nas tentativas seguintes (ler ID, pesquisar login), as
  teclas digitadas às cegas acionavam os **accesskeys** dos botões do wizard
  ('A'=Avançar, 'C'=Cancelar, 'V'=Voltar, 'F'=Finalizar) — às vezes isso
  "finalizava" o wizard por acaso (usuários 1-5 saíram CRIADO), às vezes
  deixava o modal aberto, bloqueando os usuários seguintes ("Não consegui pôr
  o foco no campo 'Usuário'" — o resto do lote falhou assim, igual à exec 9).
  **Fix (30/07, ~11:45):** `percorrer_wizard_caixa` testa **Finalizar antes
  de Avançar** e `JS_BOTAO_POR_TEXTO_PARCIAL` pula botões `disabled`.
  Validado ao vivo terminando o wizard do GLAUCIO que ficou na tela.
  Saldo da exec 10: 6 CRIADOS de verdade e 8 com ERRO, prontos para
  recadastrar (a trava de CPF pula os 6). IDs conferidos e informados pelo
  usuário, já gravados no banco:
  ALEXSANDRO.SANTOS D06/001297 · CLEYTON.NARCISO D07/001298 ·
  DANIELE.VENANCIO D08/001299 · GEOVANE.RANUSSI D09/001300 ·
  GERLAINE.SILVA D10/001301 · GLAUCIO.GASPAR D11/001302 (o wizard do GLAUCIO
  foi concluído à mão com o código novo e o registro corrigido no banco).
  Desse episódio nasceu a regra do **ID obrigatório** (`SemConfirmacaoID`,
  ver Regras de negócio): sem ler o ID, não marca CRIADO e o lote para.
- **POST-MORTEM execução nº 11 (30/07, 12:03–12:08)**: os 6 já criados foram
  pulados (`JÁ EXISTE`) ✅ e a regra do ID obrigatório interrompeu o lote na
  JANE ✅ — mas por causa de um caso novo: o `sleep(8)` fixo após o Confirmar
  foi curto (Protheus lento, "Aguarde, analisando movimentações..."), o robô
  procurou o wizard ANTES de ele existir, não achou botão e abandonou o
  wizard intocado (por isso o código do caixa ficou vazio e o ID ilegível).
  **Fixes:** (a) espera real de até 90s pelo popup do código/wizard depois do
  Confirmar; (b) `percorrer_wizard_caixa` só desiste após 5 rodadas vazias
  (~15s), não na primeira; (c) `SemConfirmacaoID` carrega login/código para o
  registro não os perder. JANE.PEREIRA existe no Protheus: **D12/001303**,
  grupo 000013 — wizard concluído à mão com o código novo (107s, incluindo o
  processamento do Finalizar) e o banco corrigido. Restam 7 para recadastrar.
- **Execuções 13–16 (30/07, tarde, filial 01LVER0023, lote de 21)**:
  exec 13 criou 5 (D20-D24/001311-001315) e parou na FRANCELISE.AMARAL (ID
  não lido → lote interrompido pela regra nova). ⚠️ Pelos códigos/IDs
  vizinhos, FRANCELISE muito provavelmente EXISTE como **D25/001316** —
  PENDENTE confirmar com o usuário e acertar a linha dela (ou usar o botão
  de criado manualmente). Execs 14/15 falharam na largada ("Trocar módulo
  não encontrado" — sobra de tela da 13, destravada manualmente). Exec 16
  criou 14 de 15 (~2 min/usuário); o único erro foi REGINA: "O grupo 000013
  não apareceu na grade" (checagem única e apressada da grade — corrigida em
  31/07 com espera de até 8s + até 2 redigitações em `preenche_grupo`).
  REGINA foi criada MANUALMENTE pelo usuário no Protheus.
- **Botão "✓ Usuário foi criado manualmente"** (31/07, pedido do usuário):
  aparece ao lado de cada linha com ERRO na tela da execução (quando não
  está rodando). Rota POST `/criado_manual/<id>`: status vira
  **CRIADO MANUALMENTE**, o CPF passa a contar na trava (que agora usa
  `LIKE 'CRIADO%'`, assim como a tela/export de usuários criados e os
  contadores), e os números da execução são recalculados. REGINA (exec 16)
  já foi marcada assim. O Protheus não é tocado pelo botão.
- **Chrome de produção encontrado FECHADO em 31/07 de manhã** (a máquina não
  reiniciou; causa desconhecida). Sem estrago: o robô reabre e reloga
  sozinho. Reaberto via smoke test de filial falsa.
- **Atualização usuário a usuário em tempo real** (pedido do usuário na
  execução nº 10): o robô agora emite `@@PARCIAL@@{json}` no stdout a cada
  usuário terminado (`_emitir_parcial` em `protheus_criar_usuario.py`) e o
  site lê o stdout **linha a linha** (`rodar_execucao` reescrito: Popen +
  loop de linhas + thread drenando stderr + `threading.Timer` como timeout),
  gravando cada linha no banco na hora via `_grava_resultado()`. Com isso o
  status vira CRIADO um a um e a pessoa já aparece na página "Usuários
  criados pela automação" durante o lote. A última linha do stdout continua
  sendo o JSON final (agora detectado por linha `[...]`, não mais por
  find("[")). ⚠️ Só vale depois de REINICIAR o site.
- **⚠️ Lição: dois sites simultâneos na 8025.** Em 30/07 ficaram DOIS
  processos `site\app_autocadastro.py` vivos ao mesmo tempo (um velho de
  10:25 e um novo de 11:03); o Windows deixou os dois com a porta e quem
  atendia era o VELHO — por isso o botão "Parar execução" "não aparecia".
  Antes de subir o site, SEMPRE matar todos os processos python com
  `site\app_autocadastro.py` na linha de comando e conferir que a página
  servida é a nova (ex.: o banner verde novo contém "reloga sozinho").
- **Projeto reorganizado em pastas** (`site/`, `robo/`, `docs/`; dados e
  configs na raiz). `BASE_DIR` dos três .py agora aponta para a raiz. Depois
  da mudança: `py_compile` OK nos 4 arquivos, smoke test do robô com filial
  falsa OK, e o site foi **reiniciado** a partir de `site\app_autocadastro.py`
  (processo em segundo plano, janela oculta — segue sendo processo manual,
  a tarefa agendada da Parte 5 continua pendente).

### Logins (para não se perder)

- **Site** (`http://10.15.17.231:8025`): `admin` / `AUTO@users10` — o usuário
  é **minúsculo e sensível a maiúsculas**. O `.env` diz `Admin`, mas o site
  lê o `protheus_config.json` (minúsculo); o usuário mandou **deixar assim**.
- **Protheus (usuário-robô)**: `AUTO.PROTHEUS` / senha no `.env`.

## O que já foi validado × o que falta

Validado: login/contexto, troca de filial, filial inexistente →
`ERRO: FILIAL NÃO EXISTE NO PROTHEUS`, criação de 1 usuário, **lote de 2 numa
filial**, os dois
grupos (000012 e 000013), cascata de login duplicado, descarte de formulário
sujo, site → robô → banco, a lista de 67 filiais com descrições, a grade de
colar do Excel (10/10 no Selenium) e o ✕ de apagar do banco local.

**Falta:**
- Lote com **duas filiais na mesma execução** (troca de filial no meio do
  lote) — único caminho não exercitado. Só acontece via CLI/JSON: pelo site
  cada execução tem uma filial só.
- Primeira **criação real nesta máquina** (o usuário pode fazer direto pelo
  site; cria de verdade no Protheus).
- **Parte 5 do SETUP_SERVIDOR.md**: tarefa agendada para o site subir com o
  Windows, energia/suspender=nunca, logon automático. A política do Chrome
  para o WebAgent (`AutoLaunchProtocolsFromOrigins`) também está pendente —
  a chave `HKCU\Software\Policies` desta máquina exige admin.
