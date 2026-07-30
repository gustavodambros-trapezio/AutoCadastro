# Seletores reais capturados do Protheus (29/07/2026)

Capturado ao vivo em `https://protheus.grupotrapezio.com.br/webapp/#`
(TOTVS WebApp 10.1.5, build 7.00.240223P) com o usuário GUSTAVO.DAMBROS.
Nada foi criado no sistema — a tela de inclusão foi mapeada e fechada com
"Fechar".

## Descoberta principal: são DUAS tecnologias diferentes

| Tela | Tecnologia | Como alcançar |
|---|---|---|
| Login + seleção inicial (Data base/Grupo/Filial/Ambiente) | Angular **PO-UI** dentro de um **iframe** (`src` contém `app-root`) | `driver.switch_to.frame(iframe)` e CSS normal |
| Módulo (menu, Trocar módulo, Cadastro de usuários) | **SmartClient web**: web components `wa-*` + **shadow DOM**, ids voláteis `COMPxxxx` | documento principal + `execute_script` varrendo `shadowRoot`; localizar por `data-advpl`, `caption` ou **texto + coordenadas** — **nunca pelo id** |

Achar o iframe do login (fica dentro de shadow DOM):

```js
function achaIframe(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    if (el.tagName === 'IFRAME' && el.src && el.src.includes('app-root')) return el;
    if (el.shadowRoot) { const r = achaIframe(el.shadowRoot); if (r) return r; }
  }
  return null;
}
```

## 1. Tela de login (dentro do iframe) — CONFIRMADO

| O que | Seletor |
|---|---|
| Campo usuário | `input[name='login']` (placeholder `Ex. sp01\nome.sobrenome`) |
| Campo senha | `input[name='password']` |
| Botão Entrar | `button.po-button` com texto `Entrar` |
| Erro de credencial | texto `Usuário não autenticado` no corpo do iframe |

## 2. Tela de seleção inicial (dentro do iframe) — CONFIRMADO

Componentes Angular estáveis: `pro-company-lookup` (Grupo),
`pro-branch-lookup` (Filial), `pro-system-module-lookup` (Ambiente),
`pro-role-lookup` (Papel de trabalho).

| O que | Seletor |
|---|---|
| Data base | `input[name='base_date']` |
| Grupo (código) | `pro-company-lookup input.po-lookup-input` |
| Grupo (descrição, readonly) | `input[name='company_description']` |
| Filial (código) | `pro-branch-lookup input.po-lookup-input` |
| Filial (descrição, readonly) | `input[name='branch_description']` |
| **Lupa da Filial** | `pro-branch-lookup .po-lookup-button-trigger` |
| Ambiente (código) | `pro-system-module-lookup input.po-lookup-input` |
| Ambiente (descrição) | `input[name='environment_description']` |
| Botões | `button.po-button` com texto `Entrar` / `Voltar` |

Confirmado: digitar `12` no Ambiente + TAB → descrição vira **"Controle de
Lojas"**. Padrões que vêm preenchidos: Grupo `01` (GRUPO TRAPEZIO), Filial
`01ALFA0001` (AUTO POSTO ALFA LTDA), Ambiente `1` (Ativo Fixo).

## 3. Consulta de filiais (modal PO-UI) — CONFIRMADO

| O que | Seletor |
|---|---|
| Campo de busca | `po-modal input[placeholder='Pesquisar']` (digitar + ENTER) |
| Linhas | `po-modal table tr` (Código, Descrição, CNPJ, Nome comercial, Empresa, Unidade, Filial) |
| Carregar mais | `button` com texto `Carregar mais resultados` |
| Confirmar seleção | `button` com texto `Selecionar` |
| Fechar | `button` com texto `Cancelar` |

⚠️ **Os nomes das filiais no Protheus não são os das abas antigas.** São
"AUTO POSTO ALFA LTDA", "AUTO POSTO ALMIRANTE" (11 unidades, diferenciadas só
pelo código!), "AUTO POSTO PETRO TRIANGULO LTDA", "R.TRAPEZIO TRIANGULO"...
Por isso o site trabalha com o **código da filial** (`01ALFA0001`). A busca
por texto funciona: `TRIANGULO` devolveu `01RTRI0001` e `01TRIA0001`.

## 4. Módulo carregado — CONFIRMADO

Popups a fechar depois de entrar:
- "Atenção - Reforma Tributária" → botão `Fechar`
- "Erro ao abrir ..." (relacionado ao WebAgent) → botão `Ok`

| O que | Como localizar |
|---|---|
| Trocar módulo | `wa-button[data-advpl='tbutton']` com `caption` = `Trocar módulo` |
| Campo Pesquisar do menu | `wa-text-input[data-advpl='tget'][placeholder='Pesquisar']` — focar via JS (`host.focus()`); `.click()` do Selenium dá `ElementNotInteractableException` |
| Itens de menu | `wa-menu-item[data-advpl='tmenuitem']` com `caption` |
| Nome do módulo | `wa-text-view` com `caption` = `Controle de Lojas` |
| Abas de rotina abertas | `wa-button` com caption tipo `Usuários [02.9.0012]` |

## 5. Janelinha de contexto / "Trocar módulo" — CONFIRMADO

É um `wa-dialog` com `wa-text-view caption='TOTVS Linha Protheus.'`. Aparece ao
clicar em `Trocar módulo` **e também** quando a sessão do SmartClient reinicia.
Campos, na ordem (`wa-text-input[data-advpl='tget']`, cada um com um `input`
interno no shadow DOM; os com lupa têm um `button` irmão):

| Ordem | Campo | Valor observado |
|---|---|---|
| 1 | Data base | `29/07/2026` |
| 2 | Grupo (código) | `01` |
| 3 | Grupo (descrição) | `GRUPO TRAPEZIO` |
| 4 | Filial (código) | `01ALFA0001` |
| 5 | Filial (descrição) | `AUTO POSTO ALFA LTDA` |
| 6 | Ambiente (código) | `12` |
| 7 | Ambiente (descrição) | `Controle de Lojas` |
| 8 | Papel de Trabalho | vazio |

Botões: `wa-button[data-advpl='tbrowsebutton']` com caption `Confirmar` /
`Cancelar` (o `tbtnbmp` "Cancelar - &lt;Ctrl-X&gt;" é o X da janela).

## 6. Caminho até o Cadastro de usuários — CONFIRMADO

**Miscelanea (18) → Usuários** (dentro do módulo 12 / Controle de Lojas).
Abre uma aba de rotina `Usuários [02.9.0012]` com o título
`Cadastro de usuários` e a barra de botões:

| Botão | Seletor |
|---|---|
| Incluir | `wa-button[data-advpl='tbrowsebutton']` caption `Incluir` |
| Alterar | idem, caption `Alterar` |
| Outras Ações | idem, caption `Outras Ações` |

A lista mostra as colunas **Id do usuário / Usuário / Nome completo do usuário /
Bloqueio de usuário / E-mail do usuário** — é daí que se lê o `ID_USUARIO`
(ex.: `000000`, `000002`, ... `000022`).

## 7. Tela de inclusão de usuário — CONFIRMADO

Abas principais (`wa-*[data-advpl='tfolder']`, y≈131):
**`Usuário`** | `Restrições de acesso` | `Parametrização`

Botões do topo: `Outras Ações` | `Fechar` | **`Confirmar`**

### Aba "Usuário" → seção "Dados do usuário"

Os labels são **texto dentro de `tpanel`**, logo acima do campo (≈15px). Método
robusto: achar o texto do label e pegar o campo (`tget`/`tcombobox`/`tcheckbox`)
com `x` parecido e `y` ≈ label.y + 15.

| Label (texto exato) | Tipo | Obs. |
|---|---|---|
| `Usuário` * | tget | o login |
| `Nome completo` * | tget | |
| `Senha` * | tget | |
| `Confirme a senha` * | tget | |
| `Usuário bloqueado` | tcombobox | vem `2 - Não` |
| `Data de bloqueio(validade)` | tget | vem `/  /` |
| `E-mail` | tget | **nunca preencher** |
| `Departamento` | tget | |
| `Cargo` | tget | |
| `Tipo do bloqueio` | tcombobox | vem `2 - Desbloqueado` |

### Aba "Usuário" → seção "Parâmetros"

| Label | Tipo | Padrão |
|---|---|---|
| `Troca periódica da senha a cada n dias` | tget | `90` |
| **`Forçar troca de senha no próx. logon`** | tcheckbox | vem **marcado** → precisa **desmarcar** |
| **`Regra de acesso por grupo`** | tcombobox | é aqui que se escolhe **Priorizar** |
| `Exigir utilização de Papel de Trabalho, quando disponível` | tcheckbox | desmarcado |
| `Número de série do Senhap` | tget | vazio |

### Sub-abas da grade (y≈470)

`Superior` | **`Grupos`** | `Papel de Trabalho`

Na sub-aba **Grupos** a grade tem as colunas **`Grupo` | `Nome` | `Prioriza`**
(cabeçalho em y≈498; a célula de Prioriza mostra `Não` por padrão). É aqui que
entra o grupo `000012`/`000013` e o Prioriza = Sim.

### Aba "Restrições de acesso"

Seção `Parâmetros de restrição de acesso` com `Número de acessos simultâneos` e
`Timeout da estação (em minutos)`; sub-abas `Horário` | `Filiais` | `Ambientes`
| `Acessos`. **Não é usada** na criação padrão.

## 8. Fluxo de gravação — VALIDADO com criação real

Criado em 29/07/2026 com autorização: **BRENDA RAMOS PINHEIRO** →
`BRENDA.PINHEIRO`, código **CZY**, id **001288**, filial `01DOMA0001`.

1. **Confirmar** (botão do topo do formulário).
2. Abre um popup: *"Foi criado um codigo de acesso para este usuario. Este
   codigo sera o numero deste caixa no sistema... **Codigo do Novo Usuario:
   CZY**"*. É daqui que sai o `CODIGO_BANCO` (regex
   `codigo do novo usuario[^A-Z0-9]{0,20}([A-Z0-9]{2,4})`). **Tem de ser
   fechado pelo botão DE DENTRO do popup** (ver armadilha nº 5).
3. Abre o wizard **"Configuração do caixa"** mostrando Codigo e Nome, com
   botões `Cancelar` | `Avançar >>`. Percorrer clicando **Avançar >>** (tudo
   padrão) e depois **Finalizar**.
   ⚠️ Os textos dos botões vêm fragmentados pelo accesskey (`"vançar >> A"`,
   `"inalizar F"`) → comparar por trecho PARCIAL, nunca exato.
   ⚠️ Precisa de **clique real** (ActionChains) — clique sintético não aciona.
4. Aparece **"Registro inserido com sucesso."**
5. O formulário fecha e a lista mostra a linha nova:
   `001288 | BRENDA.PINHEIRO | BRENDA RAMOS PINHEIRO | Não`. O `ID_USUARIO`
   é a célula de 6 dígitos à esquerda do login na mesma linha.

### Grade da sub-aba Grupos

A grade não expõe campos localizáveis por label. O que funciona: clicar na
célula **por coordenada** com clique real (a 1ª linha fica ~28px abaixo do
cabeçalho `Grupo`), digitar o código e dar **TAB** — o Protheus resolve o nome
ao lado (`000012 | GRUPO PARA CAIXAS DO PDV | Não`). Para o Prioriza, clicar na
célula da mesma linha (x entre 300 e 700) e digitar **`1`** + ENTER → vira
`Sim`.

## 9. Armadilhas descobertas na prática (todas já tratadas no código)

Estas quatro coisas fizeram o robô errar durante os testes e estão corrigidas
em `protheus_ui.py`:

1. **`Ctrl+A` NÃO seleciona o texto nos campos `wa-text-input` — ele DIGITA a
   letra "a" no campo.** Isso escrevia valores errados (chegou a deixar a
   Filial como `a`). A limpeza correta é `END` + vários `BACKSPACE`
   (`TelaProtheus._limpa`). Nos campos Angular do login (`<input>` puro) o
   `.clear()` normal funciona.
2. **`Trocar módulo` desaparece do DOM enquanto uma rotina está aberta.** Para
   trocar de filial é obrigatório fechar a rotina antes
   (`TelaProtheus.fechar_rotina`): fecha o formulário com `Fechar`, clica no X
   da aba `Usuários [02.9.0012]` e responde **`Sim`** à pergunta
   *"O processo da sessao atual sera interrompido..."*.
3. **Nunca detectar a janelinha de contexto por `TOTVS Linha Protheus`**: a
   tela de carregamento mostra *"Aguarde para utilizar o TOTVS Linha
   Protheus"* e dá falso positivo. O sinal confiável é a presença dos campos
   do diálogo (`no_dialogo_contexto`).
4. **No diálogo de contexto, casar label→campo por coordenada é frágil** (o
   diálogo se reposiciona e o label `Ambiente*` chega a alinhar com o campo do
   Grupo, gravando no lugar errado). Ali usamos a **ordem visual dos campos
   dentro do próprio diálogo** (0 Data base, 1 Grupo, 3 Filial, 5 Ambiente) e
   **conferimos o que ficou gravado** antes de confirmar. Importante: escopar a
   coleta ao diálogo — a página tem outros `tget` (o "Pesquisar" do menu, o
   filtro do browse) que embaralham a ordem.

5. **Cliques sintéticos não funcionam em vários componentes.** `element.click()`
   e cliques por JS NÃO acionam checkboxes, botões do wizard nem células de
   grade — é preciso **clique real de mouse** (`ActionChains.move_to_element().
   click()`). Pior: mexer na propriedade `checked` à mão dessincroniza o
   componente (host dizia uma coisa, tela mostrava outra).
6. **O `<input>` dentro do shadow DOM é só renderização.** Mandar `send_keys`
   para ele não escreve nada, e o `.checked` dele **nunca muda**. Para texto,
   digitar no `switch_to.active_element` e andar com **TAB**
   (`preenche_por_tab`); para estado de checkbox, ler o **host** wa-checkbox.
7. **Rajada de BACKSPACE é perigosa**: num campo vazio o Protheus joga o foco
   para o campo ANTERIOR, e o texto seguinte vai para o lugar errado. Foi o que
   deixou 'Nome completo' vazio e fez a senha acumular lixo até o Protheus
   recusar com *"Senha inválida. Utilize obrigatoriamente letras e números"* —
   e esse popup **bloqueia a tela inteira**.
8. **Popups têm de ser fechados pelo botão DE DENTRO deles.** Um
   `clica_caption('Fechar')` global acerta o `Fechar` do formulário (que vem
   antes no DOM) e o popup nunca sai. Além disso, ao procurar o popup por texto,
   vários `wa-dialog` "contêm" o texto (a janela toda inclusive) — pegar o de
   **menor área** (`fecha_popup_com_texto`).
9. **`textContent` não atravessa shadow DOM** — para achar texto de popup é
   preciso descer nos `shadowRoot` à mão.
10. **Na última etapa do wizard, "Avançar >>" fica DESABILITADO mas visível**
   (tamanho > 0). Clicar nele não faz nada e não dá erro. O loop do wizard
   precisa (a) testar **Finalizar antes de Avançar** e (b) pular botões
   `disabled` no JS. A versão que testava Avançar primeiro ficou presa 25
   tentativas por usuário (4-5 min cada) nas execuções 9 e 10 de 30/07/2026.
   Cuidado extra: os botões têm **accesskey** ('A', 'C', 'V', 'F') — digitar
   texto às cegas com o wizard aberto aciona Avançar/Cancelar/Voltar/
   Finalizar aleatoriamente.
11. **Popup "Autorização do superior"** (pede *Login do usuário* / *Senha
   atual*, botões `Cancelar`/`Finalizar`): apareceu em 30/07/2026 ao abrir a
   rotina 'Cadastro de usuários' na filial 01ALFA0001 e **bloqueou a tela** —
   um lote de 14 falhou inteiro com *"Tela 'Cadastro de usuários' não abriu"*.
   Tratamento (definido pelo usuário): clicar **Cancelar** (no botão DE DENTRO
   do popup), esperar carregar e seguir o fluxo normal — nunca `Finalizar`.
   Implementado em `cancela_autorizacao_superior()`, chamado por
   `fecha_dialogos()`.

Além disso:
- Depois do `Confirmar` do contexto, **esperar pelo sinal** (o menu lateral
  voltar) em vez de um `sleep` fixo — o tempo varia muito.
- **Ao abrir a rotina Usuários o Protheus pode pedir o contexto de novo**
  (a mesma janelinha). É só confirmar: os valores já estão corretos.
- **Filial inexistente**: o Protheus descarta o código digitado; detectamos
  isso conferindo se o código "pegou" no campo e levantamos `FilialInvalida`
  (testado com `01ZZZZ9999`).

### Ciclo validado ao vivo (29/07/2026)

```
fechar_rotina()                                  -> OK
trocar_modulo("01", "01TRIA0001", "12")          -> filial = AUTO POSTO PETRO TRIANGULO LTDA
                                                    ambiente = Controle de Lojas
abrir_cadastro_usuarios()                        -> OK (confirmou o contexto pedido de novo)
trocar_modulo("01", "01ZZZZ9999", "12")          -> FilialInvalida (como esperado)
```

## Notas operacionais

- O WebApp exige o **TOTVS WebAgent** instalado e autorizado. Em Chrome
  headless o protocolo `web-agent:` não abre → automação **só com janela
  visível**.
- A sessão do SmartClient **cai/reinicia** com certa facilidade (aparece a
  janela de contexto de novo, e às vezes o diálogo "Erro ao abrir ..." do
  WebAgent). O robô precisa detectar isso e tratar: fechar diálogos (`Ok`,
  `Fechar`) e reconfirmar o contexto.
- Login `admin`/`ADMIN` **não existe** no Protheus (dá `Usuário não
  autenticado`) — só logins nominais (ex.: `GUSTAVO.DAMBROS`).
- Filiais capturadas: veja [filiais.json](../filiais.json).
