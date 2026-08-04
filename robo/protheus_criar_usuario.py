# -*- coding: utf-8 -*-
r"""
Criação de usuários no TOTVS Protheus — Cadastro de usuários (módulo 12).

Usa os seletores REAIS capturados em 29/07/2026 (ver SELETORES_CAPTURADOS.md)
através da camada protheus_ui.py.

MODO PADRÃO: "attach" — o robô se conecta a um Chrome que JÁ ESTÁ ABERTO
no Protheus. No PC do servidor, deixe o Chrome aberto assim (atalho na área
de trabalho):

    chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\ChromeProtheus

Se a sessão estiver DESLOGADA, o robô loga sozinho com o usuário-robô do
.env (LOGIN_BOT_PROTHEUS/SENHA_BOT_PROTHEUS) e entra no módulo 12. Depois
cuida do resto: troca a filial pelo "Trocar módulo", abre Miscelanea >
Usuários e cria.

Como o site chama este script:
    python protheus_criar_usuario.py --json-b64 <base64 de uma lista JSON>

Entrada (lista JSON) — "filial" é o CÓDIGO da filial (ex.: 01ALFA0001):
    [{"row_number": 5, "nome": "FULANO DA SILVA", "cpf": "123",
      "funcao": "CAIXA", "filial": "01ALFA0001"}]

Saída (stdout = SÓ o JSON; logs vão para stderr):
    [{"row_number": 5, "filial": "01ALFA0001", "status": "CRIADO",
      "usuario": "FULANO.SILVA", "senha": "Grupo@2026", ...}]

Teste de um usuário só:
    python protheus_criar_usuario.py --nome "TESTE DA SILVA" --cpf 123 ^
        --funcao CAIXA --filial 01ALFA0001

Requisitos: pip install selenium
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import unicodedata

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protheus_ui import (TelaProtheus, FilialInvalida,  # noqa: E402
                         JS_TEM_TROCAR_MODULO, JS_TEM_ABA_ROTINA)

# ----------------------------------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------------------------------
# este arquivo mora em robo/; .env e configs ficam na RAIZ do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    with open(os.path.join(BASE_DIR, "protheus_config.json"), encoding="utf-8") as _f:
        _cfg = json.load(_f)
except (OSError, ValueError):
    _cfg = {}


def _config(env, chave, padrao=""):
    return os.environ.get(env) or _cfg.get(chave) or padrao


def _carregar_env():
    """Lê o .env da pasta (LOGIN_BOT_PROTHEUS / SENHA_BOT_PROTHEUS)."""
    env = {}
    try:
        with open(os.path.join(BASE_DIR, ".env"), encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, _, v = ln.partition("=")
                    env[k.strip()] = v.strip()
    except OSError:
        pass
    return env


_env = _carregar_env()

PROTHEUS_URL = _config("PROTHEUS_URL", "url", "https://protheus.grupotrapezio.com.br/webapp/#")
PROTHEUS_MODO = _config("PROTHEUS_MODO", "modo", "attach")     # attach (recomendado) | launch
CHROME_DEBUG = _config("PROTHEUS_CHROME_DEBUG", "chrome_debug", "127.0.0.1:9222")
# Credenciais do usuário-robô: .env da pasta (autorizado em 30/07/2026) ou
# variáveis de ambiente / config. Usadas para RELOGAR sozinho quando a sessão
# do Chrome cair, em qualquer modo.
PROTHEUS_USER = _config("PROTHEUS_USER", "usuario") or _env.get("LOGIN_BOT_PROTHEUS", "")
PROTHEUS_PASS = _config("PROTHEUS_PASS", "senha") or _env.get("SENHA_BOT_PROTHEUS", "")
CHROME_PERFIL = _config("PROTHEUS_CHROME_PERFIL", "chrome_perfil",
                        os.path.join(BASE_DIR, "chrome_perfil_robo"))
# perfil do Chrome do robô (o mesmo do atalho da área de trabalho) — usado
# quando o robô precisa ABRIR o Chrome sozinho no modo attach
CHROME_USER_DATA = _config("PROTHEUS_CHROME_USER_DATA", "chrome_user_data",
                           r"C:\ChromeProtheus")

GRUPO_EMPRESA = "01"    # Grupo: sempre 01 (GRUPO TRAPEZIO)
AMBIENTE = "12"         # Ambiente: sempre 12 (Controle de Lojas)
SENHA_PADRAO = "Grupo@2026"

# Grupos de permissão (confirmado em 29/07/2026):
#   "GERENTE" ou "LIDER DE LOJA" -> gerentes; demais -> caixas do PDV
GRUPO_CAIXAS = ("000012", "GRUPO PARA CAIXAS DO PDV")
GRUPO_GERENTES = ("000013", "GRUPO GERENTES DE UNIDADE")

CONECTORES_NOME = {"DA", "DE", "DO", "DAS", "DOS"}
MAX_TENTATIVAS_LOGIN = 15

# pedido do usuário (30/07/2026): filial inexistente é ERRO, não "aguardando"
# — o prefixo "ERRO" faz o site contar como erro e pintar de vermelho.
STATUS_FILIAL_INEXISTENTE = "ERRO: FILIAL NÃO EXISTE NO PROTHEUS"

# a trava é POR INSTÂNCIA de Chrome (porta de depuração no nome): robôs em
# Chromes diferentes (ex.: usuários na 9222, vendedores na 9223) rodam em
# paralelo; dois robôs no MESMO Chrome continuam se serializando (30/07/2026)
LOCK_PATH = os.path.join(
    os.environ.get("TEMP", "."),
    f"protheus_autocadastro_{CHROME_DEBUG.rsplit(':', 1)[-1]}.lock")
LOCK_ESPERA_MAX_S = 900
LOCK_OBSOLETO_S = 1800


def log(msg):
    print(msg, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------
# REGRAS DE NEGÓCIO
# ----------------------------------------------------------------------------
def _sem_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn")


def candidatos_login(nome_completo):
    """
    Logins na ordem de preferência (sem acentos; DA/DE/DO/DAS/DOS nunca são
    usados como sobrenome):
      PRIMEIRO.ULTIMO -> PRIMEIRO.PENULTIMO -> PRIMEIRO.ANTEPENULTIMO -> ...
      e, esgotados os nomes, PRIMEIRO.ULTIMO2, PRIMEIRO.ULTIMO3, ...
    """
    partes = [p for p in _sem_acentos(nome_completo).strip().split() if p]
    primeiro = partes[0]
    sobrenomes = [p for p in partes[1:] if p.upper() not in CONECTORES_NOME]
    if not sobrenomes:
        sobrenomes = partes[1:] or [primeiro]

    vistos = set()
    for sobrenome in reversed(sobrenomes):
        login = f"{primeiro}.{sobrenome}"
        if login.upper() not in vistos:
            vistos.add(login.upper())
            yield login

    base = f"{primeiro}.{sobrenomes[-1]}"
    n = 2
    while True:
        yield f"{base}{n}"
        n += 1


# nomes de SMART POS: começam com o número da smart e contêm "SMART"
# (vale "SMART POS" e também "SMARTPOS" escrito junto)
RE_SMART = re.compile(r"^\s*(\d+)\s.*\bSMART", re.I)


def login_smart(nome_completo, filial):
    """
    Regra do usuário (31/07/2026): quando o NOME vem de SMART POS, tudo fica
    igual (nome completo, senha, grupo...), só o LOGIN muda e é FIXO:
        "01 SMART POS LV 023" na filial 01LVER0023 -> SMARTPOS01.01LVER0023
        "02 SMART POS LV 023" na filial 01LVER0023 -> SMARTPOS02.01LVER0023
    Formato: SMARTPOS(nº que aparece no início do nome).(código da filial).
    Devolve None quando o nome não é de SMART (segue a regra normal).
    """
    m = RE_SMART.match(nome_completo or "")
    if not m:
        return None
    return f"SMARTPOS{m.group(1)}.{filial}"


def grupo_para_funcao(funcao):
    f = _sem_acentos(funcao or "").upper()
    if "GERENTE" in f or "LIDER DE LOJA" in f:
        return GRUPO_GERENTES
    return GRUPO_CAIXAS


# ----------------------------------------------------------------------------
# TRAVA DE EXECUÇÃO ÚNICA
# ----------------------------------------------------------------------------
def adquirir_trava():
    inicio = time.time()
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                idade = time.time() - os.path.getmtime(LOCK_PATH)
                if idade > LOCK_OBSOLETO_S:
                    log(f"Trava obsoleta ({int(idade)}s), removendo.")
                    os.remove(LOCK_PATH)
                    continue
            except OSError:
                continue
            if time.time() - inicio > LOCK_ESPERA_MAX_S:
                raise RuntimeError("Outra execução está rodando (trava ocupada).")
            log("Outra execução em andamento, aguardando 10s...")
            time.sleep(10)


def liberar_trava():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


# ----------------------------------------------------------------------------
# NAVEGADOR
# ----------------------------------------------------------------------------
def _abrir_chrome_robo():
    """
    Abre o Chrome do robô sozinho (mesmos parâmetros do atalho "Chrome
    Protheus (robo)") quando ele não está aberto — pedido do usuário em
    30/07/2026: ninguém precisa abrir o Chrome na mão; o robô abre e o
    garantir_sessao() loga com o usuário-robô do .env.
    """
    import subprocess
    import urllib.request

    porta = CHROME_DEBUG.rsplit(":", 1)[-1]
    caminhos = [
        _config("PROTHEUS_CHROME_EXE", "chrome_exe", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    exe = next((c for c in caminhos if c and os.path.exists(c)), None)
    if not exe:
        raise RuntimeError("Não achei o chrome.exe para abrir o Chrome do robô.")
    subprocess.Popen([
        exe,
        f"--remote-debugging-port={porta}",
        f"--user-data-dir={CHROME_USER_DATA}",
        "--no-first-run", "--no-default-browser-check",
        PROTHEUS_URL,
    ])
    fim = time.time() + 45
    while time.time() < fim:
        try:
            urllib.request.urlopen(f"http://{CHROME_DEBUG}/json/version", timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError(
        f"Abri o Chrome do robô mas a porta {CHROME_DEBUG} não respondeu.")


def conectar_navegador():
    opts = webdriver.ChromeOptions()
    if PROTHEUS_MODO == "attach":
        opts.debugger_address = CHROME_DEBUG
        try:
            driver = webdriver.Chrome(options=opts)
        except Exception:
            # Chrome do robô fechado → abre sozinho e tenta de novo
            _abrir_chrome_robo()
            try:
                driver = webdriver.Chrome(options=opts)
            except Exception as e:
                raise RuntimeError(
                    "Abri o Chrome do robô mas não consegui me conectar em "
                    f"{CHROME_DEBUG}. Detalhe: {e}")
        _focar_aba_protheus(driver)
        return driver

    opts.add_argument("--start-maximized")
    opts.add_argument(f"--user-data-dir={CHROME_PERFIL}")
    driver = webdriver.Chrome(options=opts)
    driver.get(PROTHEUS_URL)
    time.sleep(20)
    return driver


def _focar_aba_protheus(driver):
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            if "protheus" in (driver.current_url or "").lower():
                return True
        except Exception:
            continue
    return False


# Filial usada só para ENTRAR no módulo quando a sessão está deslogada; o
# lote troca para a filial certa logo depois, via trocar_modulo(). Precisa ser
# uma filial que exista — se usássemos a filial do lote e ela fosse inválida,
# o login inteiro falharia em vez de devolver ERRO: FILIAL NÃO EXISTE.
FILIAL_CONTEXTO_INICIAL = _config("PROTHEUS_FILIAL_INICIAL", "filial_inicial", "01DOMA0001")


def garantir_sessao(tela, espera_carregar=90):
    """Confere se o navegador está numa sessão logada; se não, loga sozinho
    com as credenciais do .env (fluxo validado em 30/07/2026: login PO-UI ->
    seleção de contexto -> espera o menu do módulo).

    ⚠️ A página pode estar só CARREGANDO (ex.: o robô acabou de abrir o
    Chrome sozinho): nesse momento esta_no_login() devolve False e o robô
    seguia achando que a sessão estava ok (bug real de 30/07/2026 — parou em
    "Botão 'Trocar módulo' não encontrado"). Por isso primeiro esperamos até
    conseguir AFIRMAR em que tela estamos: login, seleção de contexto ou
    módulo carregado."""
    # sessão derrubada por inatividade? o aviso "esta sessão foi encerrada por
    # inatividade / Clique aqui para voltar ao início" congela a tela — o
    # caminho seguro é recarregar a página e logar de novo (31/07/2026)
    try:
        if tela.sessao_expirada():
            log("  sessão expirada por inatividade — recarregando e relogando")
            tela.driver.get(PROTHEUS_URL)
            time.sleep(8)
    except Exception:
        pass

    fim = time.time() + espera_carregar
    estado = ""
    while time.time() < fim:
        if tela.esta_no_login():
            estado = "login"
            break
        if tela.esta_na_selecao():
            estado = "selecao"
            break
        tela._no_principal()
        # módulo no ar: menu lateral ('Trocar módulo'), OU uma rotina aberta
        # (aba [02.x] — nesse estado o menu não existe), OU o título de um
        # módulo conhecido (12=Controle de Lojas, 97=Posto Inteligente)
        if (tela._js(JS_TEM_TROCAR_MODULO) or tela._js(JS_TEM_ABA_ROTINA)
                or tela.tem_texto("Controle de Lojas")
                or tela.tem_texto("Posto Inteligente")):
            return
        log("  página do Protheus ainda carregando...")
        time.sleep(3)
    if not estado:
        return  # não deu para afirmar em que tela está; o lote reclama se preciso

    if estado == "login":
        if not (PROTHEUS_USER and PROTHEUS_PASS):
            raise RuntimeError(
                "O Chrome está na tela de LOGIN do Protheus e não há credenciais "
                "no .env (LOGIN_BOT_PROTHEUS/SENHA_BOT_PROTHEUS). Faça login "
                "manualmente nesse Chrome (módulo 12 - Controle de Lojas) e rode "
                "de novo.")
        log(f"Tela de login detectada — autenticando como {PROTHEUS_USER}...")
        tela.fazer_login(PROTHEUS_USER, PROTHEUS_PASS)
        time.sleep(3)
        if not tela.esta_na_selecao():
            time.sleep(15)
    if tela.esta_na_selecao():
        log(f"Seleção de contexto — Grupo {GRUPO_EMPRESA} / "
            f"Filial {FILIAL_CONTEXTO_INICIAL} / Ambiente {AMBIENTE}...")
        tela.selecionar_contexto_po(GRUPO_EMPRESA, FILIAL_CONTEXTO_INICIAL, AMBIENTE)
    tela.esperar_modulo_pronto(limite=240)
    log("Sessão do Protheus restabelecida.")


class SemConfirmacaoID(RuntimeError):
    """O usuário foi confirmado no Protheus mas o ID (6 dígitos) não pôde ser
    lido na lista. Regra do usuário (30/07/2026): o ID é obrigatório — sem
    ele o lote inteiro é interrompido, nunca se passa ao próximo."""


# ----------------------------------------------------------------------------
# CRIAÇÃO DE 1 USUÁRIO
# ----------------------------------------------------------------------------
def criar_usuario(tela, nome_completo, grupo_codigo, filial=""):
    """
    Cria 1 usuário na tela já aberta do Cadastro de usuários.
    Fluxo VALIDADO em 29/07/2026 criando BRENDA RAMOS PINHEIRO
    (BRENDA.PINHEIRO, código CZY, id 001288).
    Retorna (login, codigo_banco, id_usuario).
    """
    # 1) Incluir
    if not tela.clica_caption("Incluir", exato=True):
        raise RuntimeError("Botão 'Incluir' não encontrado.")
    time.sleep(10)

    # 2) Login: tenta os candidatos no próprio campo. O Protheus avisa
    #    "Não é permitido duplicação de códigos" ao sair do campo, e é ali que
    #    passamos para o próximo candidato (PRIMEIRO.ULTIMO ->
    #    PRIMEIRO.PENULTIMO -> ... -> PRIMEIRO.ULTIMO2, 3...).
    #    Exceção SMART POS (31/07/2026): login FIXO SMARTPOS(nº).(filial) —
    #    sem cascata; se já existir, é erro mesmo (o certo é apurar).
    smart = login_smart(nome_completo, filial)
    if smart:
        log(f"    nome de SMART POS — login fixo: {smart}")
        candidatos = iter([smart])
    else:
        candidatos = candidatos_login(nome_completo)
    login = tela.define_login(candidatos,
                              max_tentativas=MAX_TENTATIVAS_LOGIN)

    # 3) Demais dados. E-mail NUNCA é preenchido.
    tela.preenche_por_tab([
        ("Nome completo", nome_completo),
        ("Senha", SENHA_PADRAO),
        ("Confirme a senha", SENHA_PADRAO),
    ])

    # 4) Parâmetros
    tela.checkbox("Forçar troca de senha no próx. logon", marcado=False)
    regra = tela.seleciona_combo("priorizar")
    if not regra:
        raise RuntimeError("Não consegui definir 'Regra de acesso por grupo' = Priorizar.")
    log(f"    regra de acesso: {regra}")

    # 5) Sub-aba Grupos: grupo + Prioriza = Sim
    tela.preenche_grupo(grupo_codigo, prioriza=True)

    # 6) Confirmar
    if not tela.clica_caption("Confirmar", exato=True):
        raise RuntimeError("Botão 'Confirmar' não encontrado.")

    # 7) Popup com o código de acesso (3 caracteres) — ex.: "Codigo do Novo
    #    Usuario: CZY". Precisa ser fechado pelo botão DE DENTRO do popup.
    #    ⚠️ O tempo até ele aparecer VARIA MUITO (o Protheus mostra "Aguarde,
    #    analisando movimentações..." antes): esperar de verdade, não sleep
    #    fixo — com 8s fixos o robô passou batido na execução 11 (JANE) e o
    #    wizard "não existia ainda" quando o loop dele rodou.
    codigo_banco = ""
    fim_espera = time.time() + 90
    while time.time() < fim_espera:
        msg = tela.fecha_popup_com_texto("codigo de acesso")
        if msg:
            m = re.search(r"c[oó]digo do novo usu[aá]rio[^A-Z0-9]{0,20}([A-Z0-9]{2,4})", msg, re.I)
            if m:
                codigo_banco = m.group(1)
                log(f"    código do banco: {codigo_banco}")
            break
        if tela.tem_texto("Configuração do caixa"):
            break   # o wizard já está na tela (popup fechado antes de lermos)
        time.sleep(3)

    # 8) Wizard "Configuração do caixa" (tudo padrão) até "Registro inserido
    #    com sucesso"
    if not tela.percorrer_wizard_caixa():
        log("    aviso: não vi a mensagem de sucesso do wizard.")

    # 9) ID do usuário na lista — OBRIGATÓRIO (regra do usuário, 30/07/2026):
    #    o ID de 6 dígitos é a CONFIRMAÇÃO de que o cadastro foi gravado.
    #    Sem ele, não marcamos CRIADO e o LOTE É INTERROMPIDO — foi seguir às
    #    cegas sem essa confirmação que degradou as execuções 9 e 10 (wizard
    #    esquecido aberto bloqueando todos os usuários seguintes).
    id_usuario = ""
    for _ in range(6):
        id_usuario = _ler_id_usuario(tela, login)
        if id_usuario:
            break
        time.sleep(3)
    if not id_usuario:
        exc = SemConfirmacaoID(
            f"não consegui ler o ID do usuário {login} na lista — sem essa "
            "confirmação o lote é interrompido. Verifique no Protheus se ele "
            "foi criado (e o ID dele) antes de recadastrar.")
        # leva o que já se sabe, para não perder no registro (execução 11:
        # a JANE ficou sem login nem código no banco por isso)
        exc.login = login
        exc.codigo_banco = codigo_banco
        raise exc

    return login, codigo_banco, id_usuario


def _ler_id_usuario(tela, login):
    """Lê o ID (6 dígitos) da linha do login recém-criado na lista."""
    JS = r"""
    const login = arguments[0].toLowerCase();
    const celulas = [];
    function varre(raiz) {
      for (const el of raiz.querySelectorAll('*')) {
        const filhos = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
        if (filhos.length) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) {
            celulas.push({t: filhos.map(n => n.textContent.trim()).join(' '),
                          x: Math.round(r.x), y: Math.round(r.y)});
          }
        }
        if (el.shadowRoot) varre(el.shadowRoot);
      }
    }
    varre(document);
    const linha = celulas.find(c => c.t.toLowerCase() === login);
    if (!linha) return null;
    const id = celulas.find(c => Math.abs(c.y - linha.y) < 6 && c.x < linha.x && /^\d{6}$/.test(c.t));
    return id ? id.t : null;
    """
    for _ in range(6):
        try:
            tela._no_principal()
            valor = tela.driver.execute_script(JS, login)
            if valor and re.fullmatch(r"\d{6}", valor):
                return valor
        except Exception:
            pass
        time.sleep(2)
    return ""


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def carregar_usuarios(args):
    if args.json_b64:
        dados = json.loads(base64.b64decode(args.json_b64).decode("utf-8"))
    elif args.nome:
        dados = [{"row_number": args.row_number, "nome": args.nome,
                  "cpf": args.cpf or "", "funcao": args.funcao or "",
                  "filial": args.filial or ""}]
    elif not sys.stdin.isatty():
        dados = json.loads(sys.stdin.read())
    else:
        raise SystemExit("Uso: --json-b64 <base64> | --nome ... --cpf ... --funcao ... --filial ...")
    return [dados] if isinstance(dados, dict) else dados


def _resultado_base(u):
    grupo_codigo, grupo_nome = grupo_para_funcao(u.get("funcao"))
    return {
        "row_number": u.get("row_number", 0),
        "filial": (u.get("filial") or "").strip(),
        "filial_nome": "",   # preenchido com a descrição lida do Protheus
        "nome_completo": (u.get("nome") or "").strip(),
        "usuario": "",
        "senha": SENHA_PADRAO,
        "grupo_codigo": grupo_codigo,
        "grupo_nome": grupo_nome,
        "prioriza_grupo": "Sim",
        "forcar_troca_senha": "Não",
        "codigo_banco": "",
        "id_usuario": "",
        "status": "",
    }


def _emitir_parcial(resultados, r):
    """
    Fecha o resultado de UM usuário: guarda na lista final e avisa o site em
    tempo real com uma linha própria no stdout ("@@PARCIAL@@{json}"). O site
    atualiza a linha no banco na hora — o usuário aparece como CRIADO na tela
    e na página "Usuários criados pela automação" um a um, sem esperar o lote
    inteiro (pedido do usuário em 30/07/2026).
    """
    resultados.append(r)
    print("@@PARCIAL@@" + json.dumps(r, ensure_ascii=True), flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Cria usuários no Cadastro de usuários do Protheus (módulo 12).")
    parser.add_argument("--json-b64", help="Lista JSON de usuários em base64")
    parser.add_argument("--nome")
    parser.add_argument("--cpf")
    parser.add_argument("--funcao")
    parser.add_argument("--filial", help="CÓDIGO da filial (ex.: 01ALFA0001)")
    parser.add_argument("--row-number", type=int, default=0)
    args = parser.parse_args()

    usuarios = carregar_usuarios(args)
    grupos = {}
    for u in usuarios:
        grupos.setdefault((u.get("filial") or "").strip(), []).append(u)

    log(f"{len(usuarios)} usuário(s) em {len(grupos)} filial(is). Modo: {PROTHEUS_MODO}")

    resultados = []
    adquirir_trava()
    driver = None
    try:
        driver = conectar_navegador()
        tela = TelaProtheus(driver, log=log)
        garantir_sessao(tela)

        for filial, lista in grupos.items():
            if not filial:
                for u in lista:
                    r = _resultado_base(u)
                    r["status"] = "ERRO: filial não informada"
                    _emitir_parcial(resultados, r)
                continue

            log(f"=== Filial {filial} ({len(lista)} usuário(s)) ===")
            try:
                # Enquanto a rotina está aberta o botão 'Trocar módulo' nem
                # existe no DOM — fechar a rotina é obrigatório antes da troca.
                tela.fechar_rotina()
                tela.trocar_modulo(GRUPO_EMPRESA, filial, AMBIENTE)
                tela.abrir_cadastro_usuarios()
            except FilialInvalida:
                log(f"  Filial {filial} não existe no Protheus.")
                for u in lista:
                    r = _resultado_base(u)
                    r["status"] = STATUS_FILIAL_INEXISTENTE
                    _emitir_parcial(resultados, r)
                continue
            except Exception as e:
                log(f"  ERRO ao preparar a filial {filial}: {e}")
                for u in lista:
                    r = _resultado_base(u)
                    r["status"] = f"ERRO: filial/contexto: {e}"
                    _emitir_parcial(resultados, r)
                continue

            filial_nome = tela.ultima_filial_nome or ""
            for u in lista:
                r = _resultado_base(u)
                r["filial_nome"] = filial_nome
                log(f"Criando: {r['nome_completo']} ({u.get('funcao')}) -> grupo {r['grupo_codigo']}")
                try:
                    if not r["nome_completo"]:
                        raise RuntimeError("Nome vazio.")
                    login, codigo_banco, id_usuario = criar_usuario(
                        tela, r["nome_completo"], r["grupo_codigo"], filial)
                    r.update({"usuario": login, "codigo_banco": codigo_banco,
                              "id_usuario": id_usuario, "status": "CRIADO"})
                    log(f"  OK -> {login} | banco={codigo_banco or '?'} | id={id_usuario or '?'}")
                except SemConfirmacaoID as e:
                    # regra do usuário (30/07/2026): sem o ID lido, NUNCA
                    # passar para o próximo — interrompe o lote inteiro.
                    r.update({"usuario": getattr(e, "login", ""),
                              "codigo_banco": getattr(e, "codigo_banco", "")})
                    r["status"] = f"ERRO: {e}"
                    log(f"  ERRO em {r['nome_completo']}: {e}")
                    _emitir_parcial(resultados, r)
                    raise RuntimeError(
                        f"lote interrompido: {r['nome_completo']} ficou sem o "
                        "ID de confirmação")
                except Exception as e:
                    r["status"] = f"ERRO: {e}"
                    log(f"  ERRO em {r['nome_completo']}: {e}")
                    # volta a um estado limpo para o próximo, DESCARTANDO o que
                    # foi digitado (nunca salvar um cadastro pela metade)
                    try:
                        tela.fecha_dialogos()
                        tela.abandonar_formulario()
                        time.sleep(2)
                    except Exception as e2:
                        log(f"    aviso: não consegui limpar a tela ({e2})")
                _emitir_parcial(resultados, r)
    except Exception as e:
        log(f"ERRO FATAL: {e}")
        feitos = {(r["filial"], r["row_number"]) for r in resultados}
        for u in usuarios:
            if ((u.get("filial") or "").strip(), u.get("row_number", 0)) not in feitos:
                r = _resultado_base(u)
                r["status"] = f"ERRO: {e}"
                resultados.append(r)
    finally:
        liberar_trava()
        if driver is not None and PROTHEUS_MODO != "attach":
            try:
                driver.quit()
            except Exception:
                pass

    print(json.dumps(resultados, ensure_ascii=True))


if __name__ == "__main__":
    main()
