# -*- coding: utf-8 -*-
r"""
Preenche/atualiza as descrições das filiais no filiais.json consultando o
próprio Protheus.

Usa a janela de contexto ("Trocar módulo"): digita cada código no campo Filial
e lê a descrição que o Protheus devolve. NÃO confirma nada — só lê e, no fim,
cancela a janela, deixando a sessão como estava.

Uso (com o Chrome do robô aberto e logado no Protheus):
    python atualizar_filiais.py            # só os que estão sem descrição
    python atualizar_filiais.py --todos    # revalida todos
    python atualizar_filiais.py --codigos 01NOVO0001 01OUTRO0001

Filial que não existir mais fica marcada com descrição "(não encontrada)".
"""

import argparse
import json
import os
import sys
import time

from selenium import webdriver

# este arquivo mora em robo/; filiais.json e configs ficam na RAIZ do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protheus_ui import TelaProtheus, JS_TEM_TROCAR_MODULO  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILIAIS_PATH = os.path.join(BASE_DIR, "filiais.json")
NAO_ENCONTRADA = "(não encontrada)"

try:
    with open(os.path.join(BASE_DIR, "protheus_config.json"), encoding="utf-8") as _f:
        CHROME_DEBUG = json.load(_f).get("chrome_debug", "127.0.0.1:9222")
except (OSError, ValueError):
    CHROME_DEBUG = "127.0.0.1:9222"


def carregar():
    try:
        with open(FILIAIS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def salvar(filiais):
    filiais.sort(key=lambda f: f["codigo"])
    with open(FILIAIS_PATH, "w", encoding="utf-8") as f:
        json.dump(filiais, f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser(description="Atualiza as descrições das filiais.")
    p.add_argument("--todos", action="store_true",
                   help="revalida todas, não só as sem descrição")
    p.add_argument("--codigos", nargs="*", default=None,
                   help="lista específica de códigos para consultar/incluir")
    args = p.parse_args()

    filiais = carregar()
    por_codigo = {f["codigo"]: f for f in filiais}

    if args.codigos:
        for cod in args.codigos:
            cod = cod.strip().upper()
            if cod and cod not in por_codigo:
                novo = {"codigo": cod, "descricao": ""}
                filiais.append(novo)
                por_codigo[cod] = novo
        alvos = [c.strip().upper() for c in args.codigos if c.strip()]
    elif args.todos:
        alvos = [f["codigo"] for f in filiais]
    else:
        alvos = [f["codigo"] for f in filiais
                 if not f.get("descricao") or f["descricao"] == NAO_ENCONTRADA]

    if not alvos:
        print("Nada a atualizar — todas as filiais já têm descrição.")
        return

    print(f"Consultando {len(alvos)} filial(is) no Protheus...")

    opts = webdriver.ChromeOptions()
    opts.debugger_address = CHROME_DEBUG
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        raise SystemExit(
            f"Não consegui falar com o Chrome do Protheus em {CHROME_DEBUG}.\n"
            "Abra o Chrome pelo atalho do robô e faça login no Protheus.\n"
            f"Detalhe: {e}")

    tela = TelaProtheus(driver, log=lambda m: None)
    tela.fecha_dialogos()
    if not tela.no_dialogo_contexto():
        if not driver.execute_script(JS_TEM_TROCAR_MODULO):
            tela.fechar_rotina()
        if not tela.clica_caption("Trocar módulo", exato=True):
            raise SystemExit("Não consegui abrir a janela de contexto "
                             "('Trocar módulo'). A sessão está logada?")
        time.sleep(6)
    if not tela.no_dialogo_contexto():
        raise SystemExit("A janela de contexto não abriu.")

    atualizadas, nao_achadas = 0, 0
    try:
        for i, cod in enumerate(alvos, start=1):
            try:
                tela._contexto_escreve(tela.IDX_FILIAL, cod)
                gravado = tela._contexto_valor(tela.IDX_FILIAL)
                desc = ""
                for _ in range(4):
                    desc = tela._contexto_valor(tela.IDX_FILIAL_DESC)
                    if desc and gravado == cod:
                        break
                    time.sleep(0.8)
                if gravado != cod or not desc:
                    por_codigo[cod]["descricao"] = NAO_ENCONTRADA
                    nao_achadas += 1
                    print(f"  [{i}/{len(alvos)}] {cod}: NÃO ENCONTRADA")
                else:
                    por_codigo[cod]["descricao"] = desc
                    atualizadas += 1
                    print(f"  [{i}/{len(alvos)}] {cod}: {desc}")
            except Exception as e:
                print(f"  [{i}/{len(alvos)}] {cod}: erro ({e})")
            if i % 10 == 0:
                salvar(filiais)   # salva parcial, para não perder o trabalho
    finally:
        salvar(filiais)
        # deixa a sessão como estava
        tela.clica_caption("Cancelar", exato=True)

    print(f"\n{atualizadas} atualizada(s), {nao_achadas} não encontrada(s).")
    print(f"Arquivo: {FILIAIS_PATH}")


if __name__ == "__main__":
    main()
