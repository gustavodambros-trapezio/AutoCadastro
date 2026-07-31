r"""
Etapas 3 e 4 do cadastro completo, no módulo 97 (Posto Inteligente):

  RFID   — Atualizações > Controle de Combustíveis > Identfid
           ("Cadastro de Identificadores"): Incluir, Num. Cartao = cartão,
           Vendedor = código do vendedor, Concentrador 001 -> Confirmar.

  BANCO  — Atualizações > Cadastros > Bancos ("Atualização de Bancos"):
           o registro JÁ EXISTE (o Protheus cria junto com o usuário), então
           é ALTERAR: pesquisar pelo código do caixa (ex.: CBK), e então
             aba Cadastrais: Bco Oficial = 000
             aba Contábil:   Tipo Conta  = 1 - Caixa
             aba Outros:     Rat. Dif. Cx. = S - Sim
           -> Confirmar.

Fluxo ensinado pelo usuário em 31/07/2026 (com prints). Herda TelaVendedor
(que já tem o preenchimento devagar com a barra do numpad, o CPF mascarado
e a leitura de código no browse).
"""
import time

from selenium.webdriver.common.keys import Keys

from vendedor_ui import TelaVendedor


class TelaPosto(TelaVendedor):

    JS_COMBO_NO_ELEMENTO = r"""
    // Escolhe no combo do ELEMENTO recebido a opção que contém o texto.
    // Necessário porque seleciona_combo() global pega o PRIMEIRO combo da
    // tela com aquela opção — e na aba 'Outros' de Bancos há vários combos
    // com "Sim" (Gerente?, Rat.Dif.Cx., Integra, CIFA Ativo?).
    const host = arguments[0];
    const alvo = arguments[1].toLowerCase();
    const sel = (host.shadowRoot && host.shadowRoot.querySelector('select'))
                || host.querySelector('select');
    if (!sel) return null;
    const op = Array.from(sel.options).find(
        o => o.text.trim().toLowerCase().includes(alvo));
    if (!op) return 'SEM_OPCAO';
    sel.focus();
    sel.value = op.value;
    sel.dispatchEvent(new Event('input', {bubbles: true}));
    sel.dispatchEvent(new Event('change', {bubbles: true}));
    return op.text.trim();
    """

    def seleciona_combo_do_label(self, label, texto_opcao):
        """Combo identificado pelo LABEL ao lado/acima (não o 1º da tela)."""
        host = self.campo(label, tipos=("tcombobox",), interno=False)
        r = self._js(self.JS_COMBO_NO_ELEMENTO, host, texto_opcao)
        if not r or r == "SEM_OPCAO":
            raise RuntimeError(
                f"Combo {label!r} não tem opção contendo {texto_opcao!r} ({r}).")
        time.sleep(0.8)
        lido = self.valor_do_campo(label, tipos=("tcombobox",))
        self.log(f"    {label}: {lido or r!r}")
        return r

    # ------------------------------------------------------------- RFID
    def abrir_identfid(self):
        """Atualizações > Controle de Combustíveis > Identfid."""
        if self.tem_texto("Cadastro de Identificadores"):
            return True
        self.fecha_dialogos()
        if self.clica_caption("Identfid [", exato=False):
            time.sleep(3)
            if self.tem_texto("Cadastro de Identificadores"):
                return True
        for tentativa in range(6):
            if not self.clica_caption("Atualizações", exato=False):
                raise RuntimeError("Menu 'Atualizações' não encontrado.")
            time.sleep(3 + tentativa)
            self.clica_caption("Controle de Combustiveis", exato=False)
            time.sleep(3)
            if self.clica_caption("Identfid", exato=True):
                break
            self.log(f"  submenu do Identfid ainda não veio (tentativa {tentativa + 1})")
        fim = time.time() + 180
        while time.time() < fim:
            if self.no_dialogo_contexto():
                self.clica_caption("Confirmar", exato=True)
                time.sleep(10)
                continue
            self.fecha_dialogos(tentativas=1)
            if self.tem_texto("Cadastro de Identificadores"):
                time.sleep(2)
                return True
            time.sleep(3)
        raise RuntimeError("Tela 'Cadastro de Identificadores' não abriu.")

    def criar_rfid(self, num_cartao, codigo_vendedor, concentrador="001"):
        """Inclui o cartão RFID vinculado ao vendedor. Devolve True."""
        if not self.clica_caption("Incluir", exato=True):
            raise RuntimeError("Botão 'Incluir' do Identfid não encontrado.")
        fim = time.time() + 60
        while time.time() < fim:
            if self.tem_texto("Num. Cartao"):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Formulário do Identfid não abriu.")

        self._preenche_devagar("Num. Cartao", num_cartao)
        self._preenche_devagar("Vendedor", codigo_vendedor)
        atual = self.valor_do_campo("Concentrador") if self.campo_existe("Concentrador") else ""
        if concentrador and atual.strip() != concentrador:
            self._preenche_devagar("Concentrador", concentrador)

        if not self.clica_caption("Confirmar", exato=True):
            raise RuntimeError("Botão 'Confirmar' do Identfid não encontrado.")
        fim = time.time() + 300
        while time.time() < fim:
            self.fecha_popup_com_texto("sucesso")
            if not self.tem_texto("Num. Cartao"):
                return True          # voltou ao browse
            self.fecha_dialogos(tentativas=1)
            time.sleep(2)
        raise RuntimeError("Depois do Confirmar o Identfid não fechou.")

    # ------------------------------------------------------------ BANCO
    def abrir_bancos(self):
        """Atualizações > Cadastros > Bancos."""
        if self.tem_texto("Atualizaçäo de Bancos") or self.tem_texto("Nro Agencia"):
            return True
        self.fecha_dialogos()
        if self.clica_caption("Bancos [", exato=False):
            time.sleep(3)
            if self.tem_texto("Nro Agencia"):
                return True
        for tentativa in range(6):
            if not self.clica_caption("Atualizações", exato=False):
                raise RuntimeError("Menu 'Atualizações' não encontrado.")
            time.sleep(3 + tentativa)
            self.clica_caption("Cadastros (", exato=False)
            time.sleep(3)
            if self.clica_caption("Bancos", exato=True):
                break
            self.log(f"  submenu de Bancos ainda não veio (tentativa {tentativa + 1})")
        fim = time.time() + 180
        while time.time() < fim:
            if self.no_dialogo_contexto():
                self.clica_caption("Confirmar", exato=True)
                time.sleep(10)
                continue
            self.fecha_dialogos(tentativas=1)
            if self.tem_texto("Nro Agencia"):
                time.sleep(2)
                return True
            time.sleep(3)
        raise RuntimeError("Tela 'Atualização de Bancos' não abriu.")

    def ajustar_banco_do_caixa(self, codigo_caixa):
        """
        Acha o banco pelo código do caixa (ex.: D06) e ajusta:
        Bco Oficial=000, Tipo Conta=1-Caixa, Rat. Dif. Cx.=S-Sim.
        """
        achou = self._pesquisa_na_lista(codigo_caixa)
        if achou is None:
            raise RuntimeError("Não achei o campo de pesquisa da tela de Bancos.")
        if not achou:
            raise RuntimeError(f"Banco de código {codigo_caixa} não encontrado na lista.")
        if not self.clica_caption("Alterar", exato=True):
            raise RuntimeError("Botão 'Alterar' de Bancos não encontrado.")
        fim = time.time() + 90
        while time.time() < fim:
            if self.tem_texto("Bco Oficial"):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Formulário de Bancos não abriu.")

        # aba Cadastrais: Bco Oficial = 000
        self._preenche_devagar("Bco Oficial", "000")

        # aba Contábil: Tipo Conta = 1 - Caixa
        if not self.clica_aba("Contábil", texto_esperado="Tipo Conta"):
            raise RuntimeError("Não consegui abrir a aba 'Contábil'.")
        time.sleep(1.5)
        self.seleciona_combo_do_label("Tipo Conta", "caixa")

        # aba Outros: Rat. Dif. Cx. = S - Sim
        if not self.clica_aba("Outros", texto_esperado="Rat. Dif. Cx."):
            raise RuntimeError("Não consegui abrir a aba 'Outros'.")
        time.sleep(1.5)
        self.seleciona_combo_do_label("Rat. Dif. Cx.", "sim")

        if not self.clica_caption("Confirmar", exato=True):
            raise RuntimeError("Botão 'Confirmar' de Bancos não encontrado.")
        fim = time.time() + 300
        while time.time() < fim:
            self.fecha_popup_com_texto("sucesso")
            if not self.tem_texto("Bco Oficial"):
                return True
            self.fecha_dialogos(tentativas=1)
            time.sleep(2)
        raise RuntimeError("Depois do Confirmar o cadastro do banco não fechou.")
