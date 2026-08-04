r"""
Camada de tela do CADASTRO DE VENDEDORES (módulo 97 - Posto Inteligente).

Fluxo ensinado pelo usuário em 31/07/2026 (com prints):
  Módulo 97 -> Atualizações -> Cadastros -> Vendedores -> Incluir
  -> popup "Filiais": pesquisar pelo CÓDIGO completo (ex.: 01LVER0007) -> OK
  -> formulário "Atualização de Vendedores - INCLUIR", aba Vendas:
       Codigo       = automático (não mexer)
       Nome         = "<código do caixa> - <NOME COMPLETO>"  (ex.: CZY - BRENDA RAMOS PINHEIRO)
       Nome Reduzid = função (ex.: CAIXA/FRENTISTA)
       CNPJ/CPF     = CPF do funcionário
       Cod.Usuario  = ID do usuário (6 dígitos, ex.: 001288)
       Status       = 2 - Ativo (padrão)
  -> Salvar.

Pré-requisito: o USUÁRIO já foi criado (o vendedor usa código do caixa + ID).
Reusa TelaProtheus (attach, login, popups) sem alterar nada da produção.
"""
import time

from protheus_ui import TelaProtheus

MODULO_VENDEDORES = "97"   # Posto Inteligente


class SessaoExpirada(RuntimeError):
    """O Protheus encerrou a sessão por inatividade no meio da operação.
    ⚠️ O registro pode ter sido gravado — CONFERIR antes de tentar de novo,
    para não duplicar."""


class TelaVendedor(TelaProtheus):

    def abrir_cadastro_vendedores(self, grupo, filial, ambiente=MODULO_VENDEDORES):
        """Troca para o módulo 97 na filial pedida e abre a rotina Vendedores."""
        # já está no BROWSE de vendedores? ("Exibir Todos" + coluna Nome Reduzid;
        # obs.: o título vem como "Atualizaçäo de Vendedores" com ä — charset
        # do Protheus — então não dá para casar pelo título com acento)
        if (self.tem_texto("Exibir Todos")
                and self.tem_texto("Nome Reduzid")):
            self.log("  rotina Vendedores já está aberta — seguindo")
            return True
        self.fechar_rotina()
        self.trocar_modulo(grupo, filial, ambiente)

        self.fecha_dialogos()
        if self.clica_caption("Vendedores [", exato=False):
            time.sleep(3)
            if self.tem_texto("Nome Reduzid"):
                return True
        achou = False
        for tentativa in range(6):
            if not self.clica_caption("Atualizações", exato=False):
                raise RuntimeError("Menu 'Atualizações' não encontrado (módulo 97).")
            time.sleep(3 + tentativa)
            # o submenu vem como "Cadastros (33)" — comparar por trecho
            self.clica_caption("Cadastros (", exato=False)
            time.sleep(3)
            if self.clica_caption("Vendedores", exato=True):
                achou = True
                break
            self.log(f"  submenu de Vendedores ainda não apareceu (tentativa {tentativa + 1})")
        if not achou:
            raise RuntimeError("Item de menu 'Vendedores' não encontrado.")

        fim = time.time() + 180
        while time.time() < fim:
            # o contexto re-pedido vem PRIMEIRO (senão textos soltos do menu
            # dão falso positivo de sucesso — aconteceu no mapeamento)
            if self.no_dialogo_contexto():
                self.log("  o Protheus pediu o contexto novamente — confirmando")
                self.clica_caption("Confirmar", exato=True)
                time.sleep(10)
                continue
            self.fecha_dialogos(tentativas=1)
            # sucesso = browse de vendedores na tela (coluna 'Nome Reduzid')
            if self.tem_texto("Nome Reduzid"):
                time.sleep(2)
                return True
            time.sleep(3)
        raise RuntimeError("Tela de Vendedores não abriu.")

    # ------------------------------------------------- popup de seleção de filial
    def seleciona_filial_popup(self, filial_codigo):
        """
        Depois do Incluir PODE aparecer o popup "Filiais" — nem sempre: o
        Protheus lembra a última escolha da sessão e abre o formulário
        direto. Se o popup vier, pesquisa pelo CÓDIGO completo + ENTER (isso
        já seleciona e fecha; o OK raramente é necessário). A filial da
        SESSÃO já foi posta certa pelo abrir_cadastro_vendedores, então o
        caminho sem popup também cai na filial certa.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys
        pesquisou = False
        fim = time.time() + 45
        while time.time() < fim:
            if self.tem_texto("Cod.Usuario"):
                return True                       # formulário aberto
            if self.tem_texto("Filiais"):
                if not pesquisou:
                    self._no_principal()
                    campo = self._js(self.JS_CAMPO_PESQUISA)
                    if campo is not None:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", campo)
                        ActionChains(self.driver).move_to_element(
                            campo).pause(0.2).click().perform()
                        time.sleep(0.5)
                        ativo = self.driver.switch_to.active_element
                        ativo.send_keys(filial_codigo)
                        time.sleep(1)
                        ativo.send_keys(Keys.RETURN)
                        pesquisou = True
                        time.sleep(2.5)
                        continue
                else:
                    self._no_principal()
                    self._js(self.JS_CLICA_NO_DIALOGO, "filiais", "ok")
            time.sleep(2)
        raise RuntimeError(
            "Depois do Incluir nem o popup Filiais nem o formulário apareceram.")

    # --------------------------------------------------------- formulário
    def preencher_vendedor(self, nome_vendedor, nome_reduzido, cpf, cod_usuario):
        """
        Preenche a aba Vendas do formulário de vendedor. NÃO salva — quem
        decide entre Salvar e Cancelar é o chamador.
        """
        fim = time.time() + 60
        while time.time() < fim:
            if self.tem_texto("Cod.Usuario"):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Formulário de vendedor não abriu.")

        # o campo Nome tem 40 posições (buffer de 40 espaços) — nome maior
        # seria cortado pelo Protheus e a conferência falharia à toa
        if len(nome_vendedor) > 40:
            self.log(f"    aviso: nome de vendedor cortado em 40: {nome_vendedor!r}")
            nome_vendedor = nome_vendedor[:40].strip()
        # ⚠️ Como no cadastro de usuários: só digitação no campo FOCADO pega
        # (preenche() direto deixou o campo com espaço na 1ª posição e o
        # Protheus recusou — "Retire o espaço em branco da primeira posição").
        self.preenche_por_tab([("Nome", nome_vendedor)])
        self._preenche_devagar("Nome Reduzid", nome_reduzido)
        self._preenche_cpf(cpf)
        self.preenche_por_tab([("Cod.Usuario", cod_usuario)])
        return True

    def _preenche_devagar(self, label, valor, tentativas=3):
        """
        Digita caractere por caractere, com pausa, e confere.
        Necessário em 'Nome Reduzid': a BARRA de "CAIXA/FRENTISTA" era
        engolida quando o texto ia de uma vez (ficava "CAIXAFRENTISTA") e
        derrubou o lote de vendedores em 31/07/2026.
        """
        from selenium.webdriver.common.keys import Keys
        valor = str(valor)
        for t in range(tentativas):
            if not self.focar_campo(label):
                raise RuntimeError(f"Não consegui focar o campo {label!r}.")
            ativo = self.driver.switch_to.active_element
            atual = self.driver.execute_script("return arguments[0].value || '';", ativo)
            if atual:
                ativo.send_keys(Keys.END)
                for _ in range(len(atual)):
                    ativo.send_keys(Keys.BACK_SPACE)
            for ch in valor:
                # ⚠️ A BARRA comum é ENGOLIDA por estes campos (ficava
                # "CAIXAFRENTISTA"). A barra do teclado NUMÉRICO
                # (Keys.DIVIDE) entra normalmente — descoberto testando 4
                # formas ao vivo em 31/07/2026 (numpad OK, CDP char duplica,
                # ActionChains perde).
                self.driver.switch_to.active_element.send_keys(
                    Keys.DIVIDE if ch == "/" else ch)
                time.sleep(0.12)
            time.sleep(0.4)
            lido = self.valor_do_campo(label)
            if lido == valor:
                self.log(f"    {label}: {lido!r}")
                return True
            self.log(f"    {label}: ficou {lido!r} em vez de {valor!r} "
                     f"(tentativa {t + 1})")
            msg = self.fecha_popup_ajuda()
            if msg:
                raise RuntimeError(f"Protheus reclamou em {label!r}: {msg}")
        raise RuntimeError(f"Não consegui preencher {label!r} com {valor!r}.")

    def _preenche_cpf(self, cpf):
        """
        O campo CNPJ/CPF tem MÁSCARA (pontos/traço), então a conferência
        compara só os DÍGITOS. CPF com menos de 11 dígitos ganha zeros à
        esquerda (planilhas costumam comer o zero inicial).
        """
        from selenium.webdriver.common.keys import Keys
        digitos = "".join(c for c in str(cpf) if c.isdigit())
        if 0 < len(digitos) <= 11:
            digitos = digitos.zfill(11)
        if not self.focar_campo("CNPJ/CPF"):
            raise RuntimeError("Não consegui focar o campo 'CNPJ/CPF'.")
        ativo = self.driver.switch_to.active_element
        atual = self.driver.execute_script("return arguments[0].value || '';", ativo)
        if atual:      # limpa também buffer só de espaços
            ativo.send_keys(Keys.END)
            for _ in range(len(atual)):
                ativo.send_keys(Keys.BACK_SPACE)
        ativo.send_keys(digitos)
        time.sleep(0.5)
        lido = self.valor_do_campo("CNPJ/CPF")
        lidos = "".join(c for c in lido if c.isdigit())
        if lidos != digitos:
            raise RuntimeError(
                f"CNPJ/CPF ficou {lido!r} (dígitos {lidos!r}) em vez de {digitos!r}.")
        msg = self.fecha_popup_ajuda()
        if msg:
            raise RuntimeError(f"Protheus reclamou no CNPJ/CPF: {msg}")
        self.log(f"    CNPJ/CPF: {lido!r}")
        return True

    JS_CODIGO_VENDEDOR = r"""
    // Código (6 dígitos) da linha do browse cujo Nome é exatamente o pedido.
    const nome = arguments[0].toLowerCase();
    const celulas = [];
    function varre(raiz) {
      for (const el of raiz.querySelectorAll('*')) {
        const filhos = Array.from(el.childNodes).filter(
            n => n.nodeType === 3 && n.textContent.trim());
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
    const linha = celulas.find(c => c.t.toLowerCase() === nome);
    if (!linha) return null;
    const cod = celulas.find(c => Math.abs(c.y - linha.y) < 6
                             && c.x < linha.x && /^\d{6}$/.test(c.t));
    return cod ? cod.t : null;
    """

    def codigo_vendedor_na_lista(self, nome_vendedor):
        """Lê o código (6 dígitos) da linha do vendedor no browse, se visível."""
        self._no_principal()
        try:
            return self._js(self.JS_CODIGO_VENDEDOR, nome_vendedor[:40].strip())
        except Exception:
            return None

    def salvar_vendedor(self, nome_vendedor):
        """
        Clica Salvar e espera a CONFIRMAÇÃO FORTE: a linha nova no browse com
        o código do vendedor (mesmo espírito da regra do ID obrigatório dos
        usuários). Não confiar em "formulário sumiu": o label 'Cod.Usuario'
        continua detectável mesmo no browse (foi isso que deu falso timeout
        nos 2 primeiros saves — ambos tinham GRAVADO normalmente).
        Devolve o código do vendedor (6 dígitos).
        """
        if not self.clica_caption("Salvar", exato=True):
            raise RuntimeError("Botão 'Salvar' não encontrado.")
        # ⚠️ o Salvar do vendedor é LENTO neste servidor: passou de 240s nos
        # 3 primeiros (todos GRAVARAM, o robô só perdeu a confirmação) —
        # teto generoso de 10 min, medido em 31/07/2026
        fim = time.time() + 600
        while time.time() < fim:
            self.manter_vivo()          # a sessão morre por inatividade se esperarmos quietos
            if self.sessao_expirada():
                raise SessaoExpirada(
                    "a sessão caiu por inatividade durante o Salvar do vendedor "
                    f"{nome_vendedor!r} — o registro pode ter sido GRAVADO")
            self.fecha_popup_com_texto("sucesso")
            cod = self.codigo_vendedor_na_lista(nome_vendedor)
            if cod:
                self.log(f"    vendedor {cod} confirmado na lista")
                return cod
            self.fecha_dialogos(tentativas=1)
            time.sleep(2)
        raise RuntimeError(
            "Depois do Salvar o vendedor não apareceu na lista (sem confirmação).")

    def cancelar_vendedor(self):
        """Descarta o formulário de vendedor (testes NUNCA salvam)."""
        self.clica_caption("Cancelar", exato=True)
        time.sleep(3)
        # o Protheus pode perguntar se quer mesmo sair — responder que sim,
        # SEM salvar (mesmo padrão do 'Sair da página' do cadastro de usuários)
        if self.tem_texto("alterações não salvas"):
            self._no_principal()
            self._js(self.JS_CLICA_NO_DIALOGO, "alterações não salvas", "sair da página")
            time.sleep(3)
        for cap in ("Sim", "OK"):
            if self.tem_texto("deseja") or self.tem_texto("confirma"):
                self.clica_caption(cap, exato=True)
                time.sleep(2)
        return not self.tem_texto("Cod.Usuario")

