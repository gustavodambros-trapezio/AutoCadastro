# AutoCadastro Protheus

Site interno que cria usuários no **TOTVS Protheus** automaticamente. Em vez de
cadastrar um por um na tela do Protheus, a pessoa informa o **código da filial**,
cola a lista de funcionários e o robô faz o resto.

```
┌─────────────────────────────────────────────┐
│  AutoCadastro Protheus                      │
│                                             │
│  Filial:  01DOMA0001                        │
│                                             │
│  Funcionários (NOME;CPF;FUNÇÃO):            │
│  ┌───────────────────────────────────────┐  │
│  │ MARIA DA SILVA;12345678900;CAIXA      │  │
│  │ JOAO PEREIRA;98765432100;FRENTISTA    │  │
│  └───────────────────────────────────────┘  │
│                                             │
│           [ ▶ Criar usuários ]              │
└─────────────────────────────────────────────┘
```

Leva cerca de **1 minuto por pessoa**. A tela do resultado se atualiza sozinha e
mostra o login, a senha, o grupo, o código do caixa e o ID gerados.

## Telas

| Tela | Para que serve |
|---|---|
| **+ Novo cadastro** | Informar a filial e colar os funcionários |
| **Histórico** | Todas as execuções já feitas, com todas as colunas |
| **Usuários criados pela automação** | Só os cadastros concluídos com sucesso, separados por filial, com o botão Exportar Excel. Falhas ficam no Histórico |
| **Exportar Excel** | Baixa um `.xlsx` com uma aba por filial |

## O que o robô faz em cada usuário

1. Gera o login `PRIMEIRO.ULTIMO` (sem acentos). Se já existir, tenta
   `PRIMEIRO.PENULTIMO`, `PRIMEIRO.ANTEPENULTIMO` e, no limite,
   `PRIMEIRO.ULTIMO2`, `3`, `4`…
2. Senha padrão **Grupo@2026**, sem forçar troca no primeiro logon.
3. Regra de acesso por grupo = **Priorizar**, com **Prioriza = Sim**.
4. Grupo conforme a função:
   - contém **GERENTE** ou **LIDER DE LOJA** → `000013` (gerentes de unidade)
   - todas as demais (CAIXA, FRENTISTA, LIDER DE PISTA, LUBRIFICADOR…) → `000012` (caixas do PDV)
5. E-mail nunca é preenchido.
6. Passa pelo wizard "Configuração do caixa" com os valores padrão.
7. Anota o **código do caixa** (3 caracteres) e o **ID do usuário** (6 dígitos).

## Regras importantes

**A filial é sempre o CÓDIGO do Protheus** (`01DOMA0001`), nunca o nome. São 67
filiais cadastradas e 45 delas têm nome repetido — 26 chamadas "POSTO LINHA
VERDE" e 19 "AUTO POSTO ALMIRANTE" — então o nome não identifica nada. O campo
tem sugestões, mas aceita qualquer código digitado.

**O Chrome do Protheus precisa estar aberto e logado.** O robô usa a sessão que
já está aberta no servidor — nenhuma senha do Protheus fica guardada. Se essa
janela fechar ou deslogar, o site avisa em vermelho e bloqueia o botão de criar
até alguém relogar.

**CPF repetido não é recadastrado.** Se o CPF já foi criado antes, o site avisa
`JÁ EXISTE (login fulano.tal)` e não cria de novo.

## Situações do dia a dia

| Situação | O que fazer |
|---|---|
| Código de filial errado | As linhas voltam com `ERRO: FILIAL NÃO EXISTE NO PROTHEUS` — refaça com o código certo |
| Linha com `ERRO: ...` | Ler a mensagem, corrigir a causa e cadastrar aquela pessoa de novo |
| Site diz que o Protheus não está pronto | Reabrir o Chrome pelo atalho do robô, logar e entrar no **Ambiente 12** |
| Descobrir o código de uma filial nova | Na janela de contexto do Protheus (Trocar módulo), a lupa da Filial lista Código + Descrição |
| Filial nova não aparece nas sugestões | Ela entra sozinha na primeira vez que for usada; ou rode `python robo\atualizar_filiais.py --codigos 01NOVA0001` |

## Instalação

Passo a passo completo em **[SETUP_SERVIDOR.md](docs/SETUP_SERVIDOR.md)**. Resumo:

```powershell
pip install selenium flask waitress openpyxl
python site\app_autocadastro.py    # http://<ip-do-servidor>:8025  (rodar da raiz)
```

O site pede login (`admin` e a senha configurada em `protheus_config.json`).

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [SETUP_SERVIDOR.md](docs/SETUP_SERVIDOR.md) | Instalação no servidor, passo a passo |
| [CLAUDE.md](CLAUDE.md) | Contexto técnico do projeto (para quem for manter/alterar) |
| [SELETORES_CAPTURADOS.md](docs/SELETORES_CAPTURADOS.md) | Como as telas do Protheus foram mapeadas e as armadilhas encontradas |

## Estrutura

| Arquivo | Papel |
|---|---|
| `site/app_autocadastro.py` | O site (Flask) e o banco local SQLite |
| `robo/protheus_criar_usuario.py` | Orquestra o lote e aplica as regras de negócio |
| `robo/protheus_ui.py` | Opera a tela do Protheus (Selenium) |
| `robo/atualizar_filiais.py` | Completa a lista de filiais consultando o Protheus |
| `docs/` | Documentação técnica (setup, seletores, transferência) |
| `filiais.json` | As 67 filiais com código e descrição |
| `protheus_config.json` | Configuração (URL, porta, login do site) |
| `autocadastro.db` | Banco local: execuções e usuários criados |
