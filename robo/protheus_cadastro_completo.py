r"""
CADASTRO COMPLETO — as 4 etapas do manual, em um lote (pedido do usuário em
31/07/2026):

  1) USUÁRIO  (módulo 12)  -> código do caixa + ID
  2) VENDEDOR (módulo 97)  -> código do vendedor
  3) RFID     (Identfid)   -> só se o cartão foi informado
  4) BANCO    (Bancos)     -> Bco Oficial 000 / Tipo Conta Caixa / Rat.Dif.Cx Sim

Estratégia (uma única sessão do Protheus): FASES, não intercalado. Trocar do
módulo 12 para o 97 exige fechar a rotina e custa ~1 min, então fazer isso
por pessoa seria absurdo. Ordem: todos os usuários no 12 -> troca uma vez
para o 97 -> vendedores -> RFIDs -> bancos. Cada etapa de uma pessoa só roda
se a anterior dela deu certo (a cadeia é obrigatória).

O site recebe o andamento por linha (`@@PARCIAL@@{json}`) a cada etapa
concluída, então a tela da execução mostra as 4 colunas em tempo real.

Uso (o site chama assim):
    python robo\protheus_cadastro_completo.py --json-b64 <base64>
"""
import argparse
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import protheus_criar_usuario as base            # noqa: E402
from protheus_criar_usuario import (             # noqa: E402
    SemConfirmacaoID, candidatos_login, criar_usuario, grupo_para_funcao,
    login_smart, _resultado_base)
from banco_ui import TelaPosto                   # noqa: E402

MODULO_USUARIOS = base.AMBIENTE      # 12
MODULO_POSTO = "97"


def _emitir(r):
    print("@@PARCIAL@@" + json.dumps(r, ensure_ascii=True), flush=True)


def main():
    ap = argparse.ArgumentParser(description="Cadastro completo (4 etapas)")
    ap.add_argument("--json-b64", required=True)
    args = ap.parse_args()

    usuarios = json.loads(base64.b64decode(args.json_b64).decode("utf-8"))
    if isinstance(usuarios, dict):
        usuarios = [usuarios]
    filiais = sorted({(u.get("filial") or "").strip() for u in usuarios})
    base.log(f"{len(usuarios)} pessoa(s) · filiais {filiais} · 4 etapas")

    # estado de cada pessoa (o que já foi feito)
    fichas = []
    for u in usuarios:
        r = _resultado_base(u)
        r["rfid"] = (u.get("rfid") or "").strip()
        r["status_vendedor"] = ""
        r["codigo_vendedor"] = ""
        r["status_rfid"] = ""
        r["status_banco"] = ""
        fichas.append(r)

    base.adquirir_trava()
    try:
        driver = base.conectar_navegador()
        tela = TelaPosto(driver, log=base.log)
        base.garantir_sessao(tela)

        for filial in filiais:
            grupo = [f for f in fichas if f["filial"] == filial]

            # ---------------------------------------- ETAPA 1: usuários (12)
            base.log(f"=== [1/4] usuários · filial {filial} ===")
            try:
                tela.fechar_rotina()
                tela.trocar_modulo(base.GRUPO_EMPRESA, filial, MODULO_USUARIOS)
                tela.abrir_cadastro_usuarios()
                filial_nome = tela.ultima_filial_nome or ""
            except base.FilialInvalida:
                for f in grupo:
                    f["status"] = base.STATUS_FILIAL_INEXISTENTE
                    _emitir(f)
                continue
            except Exception as e:
                for f in grupo:
                    f["status"] = f"ERRO: filial/contexto: {e}"
                    _emitir(f)
                continue

            parar = False
            for f in grupo:
                f["filial_nome"] = filial_nome
                base.log(f"[1/4] {f['nome_completo']}")
                try:
                    login, cod_caixa, id_usuario = criar_usuario(
                        tela, f["nome_completo"], f["grupo_codigo"], filial)
                    f.update({"usuario": login, "codigo_banco": cod_caixa,
                              "id_usuario": id_usuario, "status": "CRIADO"})
                    base.log(f"  OK -> {login} | caixa={cod_caixa} | id={id_usuario}")
                except SemConfirmacaoID as e:
                    f.update({"usuario": getattr(e, "login", ""),
                              "codigo_banco": getattr(e, "codigo_banco", ""),
                              "status": f"ERRO: {e}"})
                    _emitir(f)
                    parar = True
                    break
                except Exception as e:
                    f["status"] = f"ERRO: {e}"
                    base.log(f"  ERRO: {e}")
                    try:
                        tela.fecha_dialogos()
                        tela.abandonar_formulario()
                    except Exception:
                        pass
                _emitir(f)
            if parar:
                for f in grupo:
                    if f["status"] == "PROCESSANDO":
                        f["status"] = "ERRO: lote interrompido (usuário sem ID)"
                        _emitir(f)
                continue

            prontos = [f for f in grupo if f["status"] == "CRIADO"
                       and f["codigo_banco"] and f["id_usuario"]]
            if not prontos:
                continue

            # -------------------------------------- ETAPA 2: vendedores (97)
            base.log(f"=== [2/4] vendedores · filial {filial} ===")
            try:
                tela.abrir_cadastro_vendedores(base.GRUPO_EMPRESA, filial, MODULO_POSTO)
            except Exception as e:
                for f in prontos:
                    f["status_vendedor"] = f"ERRO: {e}"
                    _emitir(f)
                continue
            for f in prontos:
                nome_v = f"{f['codigo_banco']} - {f['nome_completo']}"
                base.log(f"[2/4] {nome_v}")
                try:
                    if not tela.clica_caption("Incluir", exato=True):
                        raise RuntimeError("Botão 'Incluir' não encontrado.")
                    tela.seleciona_filial_popup(filial)
                    tela.preencher_vendedor(nome_v, f["funcao"], f["cpf"],
                                            f["id_usuario"])
                    f["codigo_vendedor"] = tela.salvar_vendedor(nome_v)
                    f["status_vendedor"] = "CRIADO"
                    base.log(f"  OK -> vendedor {f['codigo_vendedor']}")
                except Exception as e:
                    f["status_vendedor"] = f"ERRO: {e}"
                    base.log(f"  ERRO: {e}")
                    try:
                        tela.fecha_dialogos()
                        tela.cancelar_vendedor()
                    except Exception:
                        pass
                _emitir(f)

            com_vendedor = [f for f in prontos if f["codigo_vendedor"]]

            # -------------------------------------------- ETAPA 3: RFID
            com_cartao = [f for f in com_vendedor if f["rfid"]]
            for f in com_vendedor:
                if not f["rfid"]:
                    f["status_rfid"] = "PENDENTE RFID (sem cartão informado)"
                    _emitir(f)
            if com_cartao:
                base.log(f"=== [3/4] RFID · filial {filial} ===")
                try:
                    tela.fechar_rotina()
                    tela.abrir_identfid()
                except Exception as e:
                    for f in com_cartao:
                        f["status_rfid"] = f"ERRO: {e}"
                        _emitir(f)
                    com_cartao = []
                for f in com_cartao:
                    base.log(f"[3/4] cartão {f['rfid']} -> vendedor {f['codigo_vendedor']}")
                    try:
                        tela.criar_rfid(f["rfid"], f["codigo_vendedor"])
                        f["status_rfid"] = "CRIADO"
                        base.log("  OK")
                    except Exception as e:
                        f["status_rfid"] = f"ERRO: {e}"
                        base.log(f"  ERRO: {e}")
                        try:
                            tela.fecha_dialogos()
                            tela.clica_caption("Fechar", exato=True)
                        except Exception:
                            pass
                    _emitir(f)

            # -------------------------------------------- ETAPA 4: banco
            base.log(f"=== [4/4] bancos · filial {filial} ===")
            try:
                tela.fechar_rotina()
                tela.abrir_bancos()
            except Exception as e:
                for f in com_vendedor:
                    f["status_banco"] = f"ERRO: {e}"
                    _emitir(f)
                continue
            for f in com_vendedor:
                base.log(f"[4/4] banco {f['codigo_banco']}")
                try:
                    tela.ajustar_banco_do_caixa(f["codigo_banco"])
                    f["status_banco"] = "CRIADO"
                    base.log("  OK")
                except Exception as e:
                    f["status_banco"] = f"ERRO: {e}"
                    base.log(f"  ERRO: {e}")
                    try:
                        tela.fecha_dialogos()
                        tela.clica_caption("Fechar", exato=True)
                    except Exception:
                        pass
                _emitir(f)
    finally:
        base.liberar_trava()

    print(json.dumps(fichas, ensure_ascii=True))


if __name__ == "__main__":
    main()
