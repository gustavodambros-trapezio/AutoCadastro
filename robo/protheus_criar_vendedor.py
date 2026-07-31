r"""
Criação de VENDEDORES no Protheus (módulo 97) — ⚠️ EM VALIDAÇÃO.

Pré-requisito: o USUÁRIO do funcionário já existe (o vendedor usa o código do
caixa e o ID dele). Regras (ensinadas pelo usuário em 31/07/2026):
    Nome         = "<código do caixa> - <NOME>"   (ex.: CZY - BRENDA RAMOS PINHEIRO)
    Nome Reduzid = função                          (ex.: CAIXA/FRENTISTA)
    CNPJ/CPF     = CPF
    Cod.Usuario  = ID do usuário (6 dígitos)
    Filial escolhida no popup "Filiais" ao Incluir; Status padrão 2-Ativo.

Usa o MESMO Chrome da produção (9222): descobrimos em 31/07 que uma 2ª
instância de Chrome trava no "Dicionário de parametros" — a mesma trava de
execução única serializa este robô com o de usuários.

Modos de teste (não gravam nada):
    python robo\protheus_criar_vendedor.py --mapear --filial 01ALFA0001
        (só abre a rotina no módulo 97 e tira um print)
    python robo\protheus_criar_vendedor.py --teste-preencher --filial ... \
        --nome "BRENDA RAMOS PINHEIRO" --cpf 999 --funcao CAIXA \
        --codigo-banco CZY --id-usuario 001288
        (preenche o formulário e CANCELA)
Criação real (1 por vez, SÓ com autorização do usuário):
    ... --criar --filial ... --nome ... --cpf ... --funcao ... \
        --codigo-banco ... --id-usuario ...
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vendedor_ui import TelaVendedor  # noqa: E402
import protheus_criar_usuario as base  # noqa: E402


def montar_nome_vendedor(codigo_banco, nome):
    return f"{codigo_banco} - {nome}".strip()


def main():
    parser = argparse.ArgumentParser(
        description="Robô de vendedores (módulo 97) — EM VALIDAÇÃO")
    parser.add_argument("--filial", required=True)
    parser.add_argument("--nome")
    parser.add_argument("--cpf", default="")
    parser.add_argument("--funcao", default="")
    parser.add_argument("--codigo-banco", default="")
    parser.add_argument("--id-usuario", default="")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--mapear", action="store_true",
                      help="Só abre a rotina Vendedores e tira um print.")
    modo.add_argument("--teste-preencher", action="store_true",
                      help="Preenche o formulário e CANCELA (não grava).")
    modo.add_argument("--criar", action="store_true",
                      help="Cria de verdade (SÓ com autorização do usuário).")
    parser.add_argument("--print", dest="print_path", default="",
                        help="Caminho do screenshot (modos de teste)")
    args = parser.parse_args()

    base.adquirir_trava()
    driver = None
    try:
        driver = base.conectar_navegador()
        tela = TelaVendedor(driver, log=base.log)
        base.garantir_sessao(tela)

        tela.abrir_cadastro_vendedores(base.GRUPO_EMPRESA, args.filial)
        base.log("[vendedor] rotina Vendedores aberta (módulo 97).")
        if args.mapear:
            if args.print_path:
                driver.save_screenshot(args.print_path)
            return

        if not args.nome:
            raise SystemExit("--nome é obrigatório neste modo")
        if not tela.clica_caption("Incluir", exato=True):
            raise RuntimeError("Botão 'Incluir' de Vendedores não encontrado.")
        tela.seleciona_filial_popup(args.filial)

        nome_vend = montar_nome_vendedor(args.codigo_banco, args.nome)
        tela.preencher_vendedor(nome_vend, args.funcao, args.cpf, args.id_usuario)
        base.log(f"[vendedor] formulário preenchido: {nome_vend!r}")
        if args.print_path:
            driver.save_screenshot(args.print_path)

        if args.teste_preencher:
            ok = tela.cancelar_vendedor()
            base.log(f"[vendedor] TESTE: formulário descartado (fechou={ok}). Nada foi gravado.")
            return

        tela.salvar_vendedor()
        base.log(f"[vendedor] SALVO: {nome_vend}")
    finally:
        base.liberar_trava()


if __name__ == "__main__":
    main()
