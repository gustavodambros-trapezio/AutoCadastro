# O que transferir para o servidor

Jeito mais simples: **copie a pasta `AutoCadastro` inteira** para o servidor
(ex.: `C:\AutoCadastro`). Nada aqui é grande — o total dá menos de 250 KB.

Se preferir escolher arquivo por arquivo, é isso:

## Essenciais — sem estes nada funciona

| Arquivo | Por quê |
|---|---|
| `robo/protheus_ui.py` | Camada que opera a tela do Protheus (todos os seletores) |
| `robo/protheus_criar_usuario.py` | O robô: aplica as regras e cria os usuários |
| `site/app_autocadastro.py` | O site (Flask) + banco SQLite |
| `filiais.json` | As 67 filiais com código e descrição |
| `protheus_config.json` | URL, modo `attach`, porta 9222, login do site |
| `robo/atualizar_filiais.py` | Completa a lista de filiais consultando o Protheus |

## Muito recomendados

| Arquivo | Por quê |
|---|---|
| `autocadastro.db` | Contém os 3 usuários já criados. **Vale levar:** é o que impede alguém de recadastrar BRENDA, CAUA ou DAIANE por engano (a trava de CPF repetido usa este banco). Se não levar, o site começa vazio e essa proteção não vê o que já foi feito. |
| `CLAUDE.md` | Contexto técnico — é o que me situa quando eu abrir lá |
| `docs/SETUP_SERVIDOR.md` | O passo a passo da instalação |
| `README.md` | Explicação para as pessoas que vão usar |
| `docs/SELETORES_CAPTURADOS.md` | Como as telas foram mapeadas e as armadilhas do Protheus |
| `protheus_config.exemplo.json` | Modelo, caso precise recriar a configuração |

## Opcionais (referência/histórico)

| Arquivo | O que é |
|---|---|
| `criar_colaboradores.xlsx` | Sua planilha original com as pessoas a cadastrar (útil para os próximos lotes) |
| `criacao_usuarios.xlsx`, `usuarios_criados_exemplo.xlsx` | Modelos antigos de planilha |
| `README_n8n.md`, `n8n_workflow_autocadastro.json` | O caminho alternativo com n8n + Google Sheets, que abandonamos |
| `automacao_protheus_usuarios.py` | O primeiro esqueleto, antes dos seletores reais. **Não é usado** — só histórico |

## Não precisa levar

- `__pycache__/` — cache do Python, é recriado sozinho
- `chrome_perfil_robo/` — se existir, é perfil local de teste (o servidor usa `C:\ChromeProtheus`)

---

## Depois de copiar, no servidor

1. **Instalar o que falta:**
   ```powershell
   pip install selenium flask waitress openpyxl
   ```
   (Python 3.10+; Chrome e TOTVS WebAgent já devem estar na máquina)

2. **Criar o atalho do Chrome do robô** na área de trabalho:
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\ChromeProtheus https://protheus.grupotrapezio.com.br/webapp/#
   ```
   Abrir por ele, logar no Protheus e entrar no **Ambiente 12 (Controle de Lojas)**.
   Se o Chrome pedir autorização do WebAgent, marcar **"Sempre permitir"**.

3. **Conferir o `protheus_config.json`** — o `chrome_debug` tem de ser
   `127.0.0.1:9222` (é o valor que está lá).

4. **Subir o site e liberar na rede:**
   ```powershell
   python site\app_autocadastro.py
   netsh advfirewall firewall add rule name="AutoCadastro Protheus" dir=in action=allow protocol=TCP localport=8025
   ```

5. **Testar sem criar ninguém** — use um código de filial inexistente e
   confirme que volta `ERRO: FILIAL NÃO EXISTE NO PROTHEUS`:
   ```powershell
   python robo\protheus_criar_usuario.py --nome "TESTE" --cpf 000 --funcao CAIXA --filial 01ZZZZ9999
   ```

O detalhamento (tarefa agendada para subir com o Windows, energia, sessão do
Windows, política do Chrome) está no [SETUP_SERVIDOR.md](SETUP_SERVIDOR.md).

## Quando você me abrir no servidor

Peça: **"leia o CLAUDE.md e o TRANSFERIR_PARA_SERVIDOR.md e instale/teste tudo"**.

O `CLAUDE.md` tem o contexto completo: arquitetura, as regras de negócio, as 16
armadilhas do WebApp do Protheus que já custaram bug, o caminho validado na tela
e o que ainda não foi testado.

⚠️ **Vou precisar da sua autorização para criar usuários reais no teste final** —
posso validar quase tudo sem criar ninguém (preencho o formulário e descarto),
mas o teste de ponta a ponta de verdade exige criar pelo menos uma pessoa. E o
que falta exercitar é um lote com **duas filiais na mesma execução**.
