r"""
Criação de VENDEDORES no Protheus — ⚠️ EM DESENVOLVIMENTO (não é produção).

Roda SEPARADO do robô de usuários, de propósito (decisão do usuário em
30/07/2026): usa um SEGUNDO Chrome (porta 9223, perfil C:\ChromeProtheus2) e
uma trava própria (a trava leva a porta no nome), então pode rodar AO MESMO
TEMPO que o robô de usuários — o Protheus aceita duas sessões do mesmo login
(AUTO.PROTHEUS) sem derrubar uma à outra.

NÃO altera nada dos arquivos de produção: reaproveita protheus_ui.py e
protheus_criar_usuario.py por import/herança. O que for específico da tela
de vendedores vive AQUI (classe TelaVendedor).

Teste de sessão (não cria nada):
    python robo\protheus_criar_vendedor.py --so-sessao
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ambiente PRÓPRIO desta frente (segundo Chrome). Tem de ser definido ANTES
# de importar o módulo de produção, que lê essas variáveis na importação.
# Quem quiser apontar para outro lugar pode exportar as variáveis antes.
os.environ.setdefault("PROTHEUS_CHROME_DEBUG", "127.0.0.1:9223")
os.environ.setdefault("PROTHEUS_CHROME_USER_DATA", r"C:\ChromeProtheus2")

from protheus_ui import TelaProtheus  # noqa: E402
import protheus_criar_usuario as base  # noqa: E402


class TelaVendedor(TelaProtheus):
    """
    Camada de tela do CADASTRO DE VENDEDORES.
    TODO (aguardando mapeamento da tela real com o usuário):
      - abrir_cadastro_vendedores()  (caminho no menu)
      - preencher_vendedor(...)      (campos e regras)
      - confirmar / descartar        (testes SEMPRE descartam até o usuário
                                      autorizar criação real)
    """


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Robô de vendedores (EM DESENVOLVIMENTO — não usar em produção)")
    parser.add_argument("--so-sessao", action="store_true",
                        help="Só abre/loga o Chrome próprio (9223) e confere a sessão.")
    args = parser.parse_args()

    base.log(f"[vendedor] Chrome em {base.CHROME_DEBUG} | perfil {base.CHROME_USER_DATA}")
    base.adquirir_trava()
    driver = None
    try:
        driver = base.conectar_navegador()
        tela = TelaVendedor(driver, log=base.log)
        base.garantir_sessao(tela)
        base.log("[vendedor] Sessão OK no Chrome próprio.")
        if args.so_sessao:
            return
        base.log("[vendedor] TODO: fluxo de vendedor ainda não implementado "
                 "(falta mapear a tela).")
    finally:
        base.liberar_trava()


if __name__ == "__main__":
    main()
