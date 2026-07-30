# Tutorial — instalar o AutoCadastro no PC da sala de servidores

**Um site local hospedado no próprio servidor**, aberto para a rede. A pessoa
informa o **código da filial**, cola as linhas NOME;CPF;FUNÇÃO e clica em
Criar — o robô roda na própria máquina, mostra o resultado e guarda tudo num
banco local, com **Histórico**, **Planilha** (abas por filial) e **Exportar
Excel**. Sem n8n, sem Google Sheets, sem credencial OAuth.

> **Status (29/07/2026):** os seletores reais do Protheus já foram capturados e
> o fluxo completo foi **validado criando um usuário de verdade**
> (BRENDA RAMOS PINHEIRO → `BRENDA.PINHEIRO`, código CZY, id 001288, filial
> `01DOMA0001`). Detalhes técnicos em [SELETORES_CAPTURADOS.md](SELETORES_CAPTURADOS.md).

**A filial é sempre pelo CÓDIGO do Protheus** (ex.: `01DOMA0001`) — o mesmo
nome usado nas páginas/abas. Nunca o nome descritivo: há 11 filiais chamadas
"AUTO POSTO ALMIRANTE", diferenciadas só pelo código.

---

## Parte 1 — Instalar os programas (no PC do servidor)

```powershell
# Python (se "python --version" não funcionar)
winget install Python.Python.3.12
```

Feche e reabra o PowerShell, depois:

```powershell
pip install selenium flask waitress openpyxl
```

O **Google Chrome** e o **TOTVS WebAgent** já devem estar nesse PC (é por eles
que vocês acessam o Protheus). Se o WebAgent não estiver, abra
https://protheus.grupotrapezio.com.br/webapp/ no Chrome e clique em
"Instalar para Windows".

## Parte 2 — Copiar a pasta

Copie a pasta `AutoCadastro` inteira para o servidor, ex.: `C:\AutoCadastro`.
Depois copie `protheus_config.exemplo.json` para `protheus_config.json`:

```json
{
  "url": "https://protheus.grupotrapezio.com.br/webapp/#",
  "modo": "attach",
  "chrome_debug": "127.0.0.1:9222",
  "porta_site": 8025,
  "site_usuario": "admin",
  "site_senha": "AUTO@users10"
}
```

**Nenhuma senha do Protheus fica guardada.** O robô usa a sessão do Protheus
já aberta e logada (modo `attach`) — veja a Parte 3.

## Parte 3 — O Chrome do robô (sessão logada no Protheus)

Crie um atalho na área de trabalho chamado **"Chrome Protheus (robô)"** com
este destino:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\ChromeProtheus https://protheus.grupotrapezio.com.br/webapp/#
```

Abra por esse atalho, faça login no Protheus com um usuário nominal e entre no
**Ambiente 12 (Controle de Lojas)**. Deixe essa janela aberta — é nela que o
robô trabalha. Na primeira vez o Chrome pode pedir autorização para abrir o
WebAgent: marque **"Sempre permitir"** (fica salvo no perfil `C:\ChromeProtheus`).

Teste o robô sozinho:

```powershell
cd C:\AutoCadastro
python robo\protheus_criar_usuario.py --nome "TESTE AUTOMACAO SILVA" --cpf 000 --funcao CAIXA --filial 01ALFA0001
```

## Parte 4 — Subir o site

```powershell
cd C:\AutoCadastro
python site\app_autocadastro.py
```

Deve aparecer `AutoCadastro no ar: http://0.0.0.0:8025` e a situação da conexão
com o Chrome do Protheus. Teste em http://localhost:8025 (login `admin` /
`AUTO@users10`).

**Abrir para a rede** (uma vez, PowerShell como administrador):

```powershell
netsh advfirewall firewall add rule name="AutoCadastro Protheus" dir=in action=allow protocol=TCP localport=8025
```

Descubra o IP com `ipconfig` e passe o link para a equipe (ex.:
`http://10.15.17.231:8025`).

## Parte 5 — Deixar o site sempre no ar

1. **Agendador de Tarefas** > Criar Tarefa:
   - Geral: "Executar estando o usuário conectado ou não" + "Com privilégios
     mais altos"
   - Disparadores: "Ao inicializar"
   - Ações: Programa = caminho do `python.exe` (`(Get-Command python).Source`),
     Argumentos = `C:\AutoCadastro\site\app_autocadastro.py`,
     Iniciar em = `C:\AutoCadastro`
   - Configurações: "Se a tarefa falhar, reiniciar a cada 1 minuto"
2. **Sessão do Windows:** o Chrome do robô precisa de sessão ativa. Deixe o
   usuário logado e, ao sair do acesso remoto, **desconecte** (X da janela) —
   nunca use Sair/Logoff. Se a máquina reiniciar, alguém precisa reabrir o
   atalho do Chrome e relogar no Protheus (configure logon automático com
   `netplwiz` para facilitar).
3. **Energia:** Opções de Energia > Suspender = Nunca.
4. *(Opcional, evita a janelinha do WebAgent)* Política do Chrome, como admin:

```powershell
New-Item -Path "HKCU:\Software\Policies\Google\Chrome" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Policies\Google\Chrome" -Name "AutoLaunchProtocolsFromOrigins" -Value '[{"protocol":"web-agent","allowed_origins":["https://protheus.grupotrapezio.com.br"]}]'
```

## Parte 6 — Operação do dia a dia

| O que fazer | Como |
|---|---|
| Cadastrar funcionários | Abrir o site > digitar o **código da filial** (`01DOMA0001`; há sugestões, mas aceita qualquer código) > colar as linhas NOME;CPF;FUNÇÃO (pode colar do Excel) > **Criar usuários** |
| Acompanhar | A página do resultado atualiza sozinha; verde = CRIADO (~1 min por pessoa) |
| Código de filial errado | As linhas voltam `ERRO: FILIAL NÃO EXISTE NO PROTHEUS` — refaça com o código certo |
| Descobrir o código de uma filial | No Protheus, na janela de contexto (Trocar módulo), a lupa da Filial lista Código + Descrição. Padrão: `01` + mnemônico + `0001` |
| CPF repetido | O site avisa `JÁ EXISTE (login fulano.tal)` e não cria de novo |
| Linha com `ERRO: ...` | Corrigir a causa e cadastrar aquela pessoa de novo |
| Ver execuções antigas | Botão **Histórico** (clique no nº para ver todas as colunas) |
| Ver todos os criados | Botão **Planilha** (abas por filial) ou **Exportar Excel** |
| Site diz que o Protheus não está pronto | O Chrome do robô fechou ou deslogou — reabra pelo atalho, logue e entre no Ambiente 12 |

## Regras que o robô aplica

- Login `PRIMEIRO.ULTIMO`; se existir, `PRIMEIRO.PENULTIMO`,
  `PRIMEIRO.ANTEPENULTIMO` e depois `PRIMEIRO.ULTIMO2`, `3`… (conectores
  DA/DE/DO/DAS/DOS nunca entram)
- Senha `Grupo@2026`, **sem** forçar troca no primeiro logon
- Regra de acesso por grupo = **1 - Priorizar**; Prioriza = **Sim**
- Grupo: funções com GERENTE ou LIDER DE LOJA → **000013** (gerentes de
  unidade); todas as demais → **000012** (caixas do PDV)
- E-mail nunca é preenchido
- Wizard "Configuração do caixa" avança com todos os valores padrão
- O Protheus gera o **código do caixa** (3 caracteres, ex.: CZY) e o
  **ID do usuário** (6 dígitos, ex.: 001288) — ambos são gravados na planilha
