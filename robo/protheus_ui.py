# -*- coding: utf-8 -*-
r"""
Camada de acesso à tela do TOTVS Protheus WebApp (seletores REAIS, capturados
em 29/07/2026 — ver SELETORES_CAPTURADOS.md).

Duas tecnologias convivem na mesma página:
  * Login e seleção de contexto: Angular PO-UI dentro de um IFRAME
    (src contém "app-root") -> CSS normal depois de switch_to.frame
  * Módulo/Cadastro de usuários: SmartClient web com componentes wa-* em
    SHADOW DOM e ids voláteis (COMPxxxx) -> localizar por data-advpl, caption
    ou texto+coordenadas, SEMPRE via execute_script

Este módulo não sabe nada de planilha/site: só sabe operar a tela.
"""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# ----------------------------------------------------------------------------
# JS auxiliares (varrem shadow DOM)
# ----------------------------------------------------------------------------
JS_ACHA_IFRAME = r"""
function acha(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    if (el.tagName === 'IFRAME' && el.src && el.src.includes('app-root')) return el;
    if (el.shadowRoot) { const r = acha(el.shadowRoot); if (r) return r; }
  }
  return null;
}
return acha(document);
"""

# clica um wa-button/wa-menu-item pelo caption (limpo de tags HTML)
JS_CLICA_CAPTION = r"""
const alvo = arguments[0].toLowerCase();
const exato = arguments[1] === true;
function limpa(s) { return (s || '').replace(/<[^>]+>/g, '').trim().toLowerCase(); }
function acha(raiz) {
  for (const el of raiz.querySelectorAll('wa-button, wa-menu-item, wa-tab-button')) {
    const cap = limpa(el.getAttribute('caption')) || limpa(el.textContent);
    if (cap && (exato ? cap === alvo : cap.includes(alvo))) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return el;
    }
    if (el.shadowRoot) { const r = acha(el.shadowRoot); if (r) return r; }
  }
  for (const el of raiz.querySelectorAll('*')) {
    if (el.shadowRoot) { const r = acha(el.shadowRoot); if (r) return r; }
  }
  return null;
}
const b = acha(document);
if (!b) return null;
b.click();
return (b.getAttribute('caption') || b.textContent || 'ok').replace(/<[^>]+>/g, '').trim().substring(0, 60);
"""

# clica qualquer elemento visível cujo texto seja exatamente o alvo (abas, etc.)
JS_CLICA_TEXTO = r"""
const alvo = arguments[0].toLowerCase();
function acha(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    if ((el.textContent || '').trim().toLowerCase() === alvo) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return el;
    }
    if (el.shadowRoot) { const r2 = acha(el.shadowRoot); if (r2) return r2; }
  }
  return null;
}
const el = acha(document);
if (!el) return null;
el.click();
return 'ok';
"""

# existe algum texto contendo o trecho? (para popups de erro/duplicidade)
JS_TEM_TEXTO = r"""
const alvo = arguments[0].toLowerCase();
function busca(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    const filhos = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
    if (filhos.length) {
      const t = filhos.map(n => n.textContent).join(' ').toLowerCase();
      if (t.includes(alvo)) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) return filhos.map(n => n.textContent.trim()).join(' ');
      }
    }
    if (el.shadowRoot) { const r2 = busca(el.shadowRoot); if (r2) return r2; }
  }
  return null;
}
return busca(document);
"""

# mapa de labels e campos (tget/tcombobox/tcheckbox) com coordenadas.
# Os labels aparecem de DUAS formas no Protheus, e as duas são coletadas:
#   * como texto solto dentro de tpanel (tela de inclusão de usuário)
#   * no atributo caption de wa-text-view (janelinha de contexto/Trocar módulo)
JS_MAPA_CAMPOS = r"""
const labels = [], campos = [];
function limpa(s) { return (s || '').replace(/<[^>]+>/g, '').trim(); }
function varre(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    const advpl = el.getAttribute && el.getAttribute('data-advpl');
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      if (advpl && ['tget', 'tcombobox', 'tcheckbox', 'tmultiget'].includes(advpl)) {
        campos.push({advpl, x: Math.round(r.x), y: Math.round(r.y), el});
      } else {
        const cap = limpa(el.getAttribute && el.getAttribute('caption'));
        if (cap) {
          labels.push({texto: cap, x: Math.round(r.x), y: Math.round(r.y)});
        }
        const filhos = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
        if (filhos.length) {
          labels.push({texto: filhos.map(n => n.textContent.trim()).join(' '),
                       x: Math.round(r.x), y: Math.round(r.y)});
        }
      }
    }
    if (el.shadowRoot) varre(el.shadowRoot);
  }
}
varre(document);
window.__ac_campos = campos;   // guarda para o clique/preenchimento
return {labels: labels.map(l => ({texto: l.texto, x: l.x, y: l.y})),
        campos: campos.map(c => ({advpl: c.advpl, x: c.x, y: c.y}))};
"""

# devolve o elemento do campo cujo índice foi calculado em Python (o host wa-*)
JS_CAMPO_POR_INDICE = r"""
const i = arguments[0];
const c = (window.__ac_campos || [])[i];
return c ? c.el : null;
"""

# Devolve o <input> REAL dentro do shadow DOM do componente. Clicar no host
# wa-text-input NÃO dá foco ao input interno — as teclas se perdem e o campo
# fica vazio (bug observado: só o primeiro campo, que o Protheus já focava
# sozinho, era preenchido). Sempre operar o elemento interno.
JS_CAMPO_INTERNO = r"""
const i = arguments[0];
const c = (window.__ac_campos || [])[i];
if (!c) return null;
const host = c.el;
if (host.shadowRoot) {
  const inp = host.shadowRoot.querySelector('input, textarea, select');
  if (inp) return inp;
}
const inp2 = host.querySelector && host.querySelector('input, textarea, select');
return inp2 || host;
"""

# Campos (tget) que estão DENTRO do diálogo de contexto, em ordem visual.
# Precisa ser escopado ao diálogo: a página tem outros tget (o "Pesquisar" do
# menu, o filtro do browse), e pegá-los embaralha a ordem dos campos.
JS_CAMPOS_CONTEXTO = r"""
function limpa(s) { return (s || '').replace(/<[^>]+>/g, '').trim(); }
function temDataBase(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    const cap = limpa(el.getAttribute && el.getAttribute('caption'));
    if (cap === 'Data base*' || cap === 'Data base') return true;
    if (el.shadowRoot && temDataBase(el.shadowRoot)) return true;
  }
  return false;
}
function achaDialogo(raiz) {
  for (const el of raiz.querySelectorAll('wa-dialog')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && temDataBase(el)) return el;
    if (el.shadowRoot) { const d = achaDialogo(el.shadowRoot); if (d) return d; }
  }
  for (const el of raiz.querySelectorAll('*')) {
    if (el.shadowRoot) { const d = achaDialogo(el.shadowRoot); if (d) return d; }
  }
  return null;
}
const dlg = achaDialogo(document);
if (!dlg) return null;
const campos = [];
function varre(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    if (el.getAttribute && el.getAttribute('data-advpl') === 'tget') {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        campos.push({x: Math.round(r.x), y: Math.round(r.y), el});
      }
    }
    if (el.shadowRoot) varre(el.shadowRoot);
  }
}
varre(dlg);
campos.sort((a, b) => (a.y - b.y) || (a.x - b.x));
window.__ac_ctx = campos;
return campos.map(c => ({x: c.x, y: c.y}));
"""

# Nos campos da janela de CONTEXTO o que funciona é operar o HOST wa-text-input
# (não o <input> do shadow DOM). Testado: com o host, a troca de filial grava;
# trocando para o input interno, a digitação é ignorada e o valor não muda.
# (No formulário de usuário é o contrário — lá se digita no campo focado.)
JS_CTX_POR_INDICE = r"""
const c = (window.__ac_ctx || [])[arguments[0]];
return c ? c.el : null;
"""

# Valor do campo de contexto: o host expõe .value; se não, cai no input interno
JS_CTX_VALOR = r"""
const c = (window.__ac_ctx || [])[arguments[0]];
if (!c) return null;
const host = c.el;
if (host.value !== undefined && host.value !== null && String(host.value) !== '') {
  return String(host.value);
}
const inp = (host.shadowRoot && host.shadowRoot.querySelector('input')) ||
            (host.querySelector && host.querySelector('input'));
return inp ? String(inp.value || '') : String(host.value || '');
"""

# Botão por texto PARCIAL (os botões do wizard vêm com o texto fragmentado
# pelo accesskey: "vançar >> A", "inalizar F").
JS_BOTAO_POR_TEXTO_PARCIAL = r"""
const alvo = arguments[0];
let achado = null;
function varre(raiz) {
  for (const el of raiz.querySelectorAll('wa-button, button')) {
    const t = ((el.textContent || '') + ' ' +
               ((el.getAttribute && el.getAttribute('caption')) || ''))
              .replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
    // botão desabilitado continua VISÍVEL (a última etapa do wizard mostra um
    // "Avançar >>" morto) — clicar nele não faz nada, então é pulado aqui
    const desab = el.disabled || (el.hasAttribute && el.hasAttribute('disabled'));
    if (t.includes(alvo) && !t.includes('ctrl') && !desab) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) { achado = el; return true; }
    }
    if (el.shadowRoot && varre(el.shadowRoot)) return true;
  }
  return false;
}
varre(document);
return achado;
"""

# Célula da grade de grupos (coluna Grupo / Prioriza) por coordenada
JS_ELEMENTO_NO_PONTO = r"""
let el = document.elementFromPoint(arguments[0], arguments[1]);
while (el && el.shadowRoot) {
  const d = el.shadowRoot.elementFromPoint(arguments[0], arguments[1]);
  if (!d || d === el) break;
  el = d;
}
return el;
"""

# Células visíveis com coordenadas, SEM filtro fixo de posição: o formulário
# rola conforme os campos recebem foco, então fixar "y > 490" fazia o
# cabeçalho da grade desaparecer (bug real: "Cabeçalho 'Grupo' não encontrado").
JS_CELULAS_GRADE_GRUPOS = r"""
const cels = [];
function varre(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    const filhos = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
    if (filhos.length) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        cels.push({y: Math.round(r.y), x: Math.round(r.x),
                   cy: Math.round(r.y + r.height / 2), cx: Math.round(r.x + r.width / 2),
                   t: filhos.map(n => n.textContent.trim()).join(' ').substring(0, 40)});
      }
    }
    if (el.shadowRoot) varre(el.shadowRoot);
  }
}
varre(document);
cels.sort((a, b) => (a.y - b.y) || (a.x - b.x));
return cels;
"""

# o botão "Trocar módulo" só existe no DOM quando nenhuma rotina está aberta
JS_TEM_TROCAR_MODULO = r"""
function acha(raiz) {
  for (const el of raiz.querySelectorAll('wa-button')) {
    const cap = (el.getAttribute('caption') || '').replace(/<[^>]+>/g, '').trim();
    if (cap === 'Trocar módulo') {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return true;
    }
    if (el.shadowRoot) { if (acha(el.shadowRoot)) return true; }
  }
  for (const el of raiz.querySelectorAll('*')) {
    if (el.shadowRoot) { if (acha(el.shadowRoot)) return true; }
  }
  return false;
}
return acha(document);
"""

# existe alguma ABA de rotina aberta? (caption tipo 'Vendedores [02.9.0097]')
JS_TEM_ABA_ROTINA = r"""
function acha(raiz) {
  for (const el of raiz.querySelectorAll('*')) {
    const cap = el.getAttribute && el.getAttribute('caption');
    if (cap && cap.includes('[02.')) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return true;
    }
    if (el.shadowRoot) { if (acha(el.shadowRoot)) return true; }
  }
  return false;
}
return acha(document);
"""

# fecha a aba de uma rotina aberta (ex.: "Usuários [02.9.0012]") clicando no X
JS_FECHA_ABA_ROTINA = r"""
function achaAba(raiz) {
  for (const el of raiz.querySelectorAll('wa-tab-button')) {
    const t = (el.textContent || '').trim();
    // abas de rotina têm o nome + versão entre colchetes
    if (/\[\d+\.\d+\.\d+\]/.test(t)) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return el;
    }
    if (el.shadowRoot) { const rr = achaAba(el.shadowRoot); if (rr) return rr; }
  }
  for (const el of raiz.querySelectorAll('*')) {
    if (el.shadowRoot) { const rr = achaAba(el.shadowRoot); if (rr) return rr; }
  }
  return null;
}
const aba = achaAba(document);
if (!aba) return null;
const nome = (aba.textContent || '').trim().substring(0, 40);
// o X é o elemento pequeno mais à direita dentro da aba
const raizes = [aba, aba.shadowRoot].filter(Boolean);
let fechar = null;
for (const raiz of raizes) {
  for (const c of raiz.querySelectorAll('*')) {
    const rc = c.getBoundingClientRect();
    if (rc.width > 4 && rc.width < 26 && rc.height > 4 && rc.height < 26) {
      if (!fechar || rc.x > fechar.getBoundingClientRect().x) fechar = c;
    }
  }
}
(fechar || aba).click();
return nome;
"""


class TelaProtheus:
    """Opera a tela do Protheus WebApp. Não faz login com senha por padrão:
    o padrão é usar uma sessão que JÁ ESTÁ logada no navegador."""

    def __init__(self, driver, log=print, timeout=60):
        self.driver = driver
        self.log = log
        self.timeout = timeout
        # descrição da última filial selecionada (lida do próprio Protheus)
        self.ultima_filial_nome = ""

    # -------------------------------------------------------------- utilidades
    def _js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def _no_iframe(self):
        """Entra no iframe do PO-UI (telas de login/contexto)."""
        self.driver.switch_to.default_content()
        iframe = self._js(JS_ACHA_IFRAME)
        if iframe is None:
            return False
        self.driver.switch_to.frame(iframe)
        return True

    def _no_principal(self):
        self.driver.switch_to.default_content()

    def clica_caption(self, caption, exato=True):
        self._no_principal()
        return self._js(JS_CLICA_CAPTION, caption, exato)

    def clica_texto(self, texto):
        self._no_principal()
        return self._js(JS_CLICA_TEXTO, texto)

    def tem_texto(self, trecho):
        self._no_principal()
        return self._js(JS_TEM_TEXTO, trecho)

    JS_FECHA_POPUP_AJUDA = r"""
    // Fecha o popup de validação clicando no botão DENTRO dele. Um
    // clica_caption('Fechar') global acerta o 'Fechar' do formulário (que vem
    // antes no DOM) e o popup nunca sai — foi o que travou tudo.
    // ATENÇÃO: textContent NÃO atravessa shadow DOM — é preciso descer nos
    // shadowRoots à mão para achar o texto do popup (foi o que fez a busca
    // falhar e o popup parecer inexistente).
    function texto(raiz) {
      let out = '';
      const pilha = [raiz];
      while (pilha.length) {
        const no = pilha.pop();
        if (!no) continue;
        for (const filho of (no.childNodes || [])) {
          if (filho.nodeType === 3) out += ' ' + filho.textContent;
          else pilha.push(filho);
        }
        if (no.shadowRoot) pilha.push(no.shadowRoot);
      }
      return out.replace(/\s+/g, ' ').trim();
    }
    // Vários wa-dialog "contêm" o texto (a janela inteira também). O popup é
    // o MENOR deles — pegar o maior faria clicar no botão errado.
    const candidatos = [];
    function coleta(raiz) {
      for (const el of raiz.querySelectorAll('wa-dialog')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && /Problema:/i.test(texto(el))) {
          candidatos.push({el, area: r.width * r.height});
        }
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
      for (const el of raiz.querySelectorAll('*')) {
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
    }
    coleta(document);
    candidatos.sort((a, b) => a.area - b.area);
    const popup = candidatos.length ? candidatos[0].el : null;
    if (!popup) return null;
    const msg = texto(popup).substring(0, 300);
    let botao = null;
    function achaBotao(raiz) {
      for (const el of raiz.querySelectorAll('wa-button, button')) {
        const t = (el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const cap = (el.getAttribute && (el.getAttribute('caption') || '') || '')
                      .replace(/<[^>]+>/g, '').trim().toLowerCase();
        if (t === 'fechar' || cap === 'fechar' || t === 'ok' || cap === 'ok') {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) { botao = el; return true; }
        }
        if (el.shadowRoot && achaBotao(el.shadowRoot)) return true;
      }
      return false;
    }
    achaBotao(popup);
    if (popup.shadowRoot) achaBotao(popup.shadowRoot);
    if (botao) { botao.click(); return msg; }
    return 'SEM_BOTAO: ' + msg;
    """

    JS_FECHA_POPUP_COM_TEXTO = r"""
    // Fecha o MENOR wa-dialog que contenha o trecho pedido, clicando num botão
    // DENTRO dele. Necessário porque um clique global em 'Fechar' acerta o
    // botão do formulário (que vem antes no DOM) e o popup nunca sai.
    const trecho = arguments[0].toLowerCase();
    function texto(raiz) {
      let out = '';
      const pilha = [raiz];
      const vistos = new Set();
      while (pilha.length) {
        const no = pilha.pop();
        if (!no || vistos.has(no)) continue;
        vistos.add(no);
        for (const f of (no.childNodes || [])) {
          if (f.nodeType === 3) out += ' ' + f.textContent;
          else pilha.push(f);
        }
        if (no.shadowRoot) pilha.push(no.shadowRoot);
      }
      return out.replace(/\s+/g, ' ').trim();
    }
    const candidatos = [];
    function coleta(raiz) {
      for (const el of raiz.querySelectorAll('wa-dialog')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && texto(el).toLowerCase().includes(trecho)) {
          candidatos.push({el, area: r.width * r.height});
        }
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
      for (const el of raiz.querySelectorAll('*')) {
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
    }
    coleta(document);
    if (!candidatos.length) return null;
    candidatos.sort((a, b) => a.area - b.area);
    const popup = candidatos[0].el;
    const msg = texto(popup).substring(0, 800);
    let botao = null;
    function achaBotao(raiz) {
      for (const el of raiz.querySelectorAll('wa-button, button')) {
        const t = ((el.textContent || '') + ' ' +
                   ((el.getAttribute && el.getAttribute('caption')) || ''))
                  .replace(/<[^>]+>/g, '').toLowerCase();
        if (/\b(fechar|ok|sim|confirmar|finalizar)\b/.test(t) && !/ctrl/.test(t)) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) { botao = el; return true; }
        }
        if (el.shadowRoot && achaBotao(el.shadowRoot)) return true;
      }
      return false;
    }
    achaBotao(popup);
    if (popup.shadowRoot) achaBotao(popup.shadowRoot);
    if (botao) { botao.click(); return msg; }
    return 'SEM_BOTAO: ' + msg;
    """

    def fecha_popup_com_texto(self, trecho):
        """
        Fecha o popup que contém `trecho` (clicando num botão DENTRO dele) e
        devolve o texto completo do popup — útil para ler o código do banco.
        """
        self._no_principal()
        msg = self._js(self.JS_FECHA_POPUP_COM_TEXTO, trecho)
        if msg:
            time.sleep(2)
        return msg

    def popup_ajuda(self):
        """
        Detecta o popup de validação do Protheus ("Help: <campo> / Problema:
        ... / Solução: ...") e devolve o texto do problema, ou None.
        Esse modal BLOQUEIA a tela: enquanto ele está aberto nada é preenchido
        e os cliques em 'Fechar' acertam ele, não o formulário.
        """
        if not self.tem_texto("problema:"):
            return None
        texto = self.tem_texto("problema:") or ""
        return texto.strip()

    def fecha_popup_ajuda(self):
        """Fecha o popup de validação e devolve a mensagem (ou None)."""
        self._no_principal()
        msg = self._js(self.JS_FECHA_POPUP_AJUDA)
        if not msg:
            return None
        time.sleep(1.5)
        if str(msg).startswith("SEM_BOTAO"):
            # sem botão alcançável: ESC costuma fechar os diálogos do Protheus
            try:
                self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
                time.sleep(1.5)
            except Exception:
                pass
        return msg

    def confirma_interrupcao_sessao(self):
        """
        Responde 'Sim' à pergunta que aparece ao fechar a aba de uma rotina:
        "O processo da sessao atual sera interrompido. Tem certeza que deseja
        fecha-la?". Só clica 'Sim' se ESSA pergunta estiver na tela — nunca
        um 'Sim' genérico (poderia confirmar outra coisa por engano).
        """
        if self.tem_texto("processo da sess"):
            return bool(self.clica_caption("Sim", exato=True))
        return False

    def cancela_autorizacao_superior(self):
        """
        Cancela o popup "Autorização do superior" (pede 'Login do usuário' /
        'Senha atual' e tem botões Cancelar/Finalizar). Apareceu em 30/07/2026
        ao abrir a rotina 'Cadastro de usuários' (filial 01ALFA0001) e BLOQUEIA
        a tela — um lote de 14 falhou inteiro com "Tela ... não abriu".
        Tratamento definido pelo usuário: clicar **Cancelar**, esperar a tela
        carregar e seguir o fluxo normal. NUNCA clicar em 'Finalizar' (tentaria
        autenticar com os campos vazios). O clique tem de ser num botão DE
        DENTRO do popup — um 'Cancelar' global poderia acertar outro botão.
        """
        if not self.tem_texto("autorização do superior"):
            return False
        self._no_principal()
        r = self._js(self.JS_CLICA_NO_DIALOGO,
                     "autorização do superior", "cancelar")
        self.log(f"  popup 'Autorização do superior' na tela — cancelando ({r})")
        if r != "ok":
            # fallback: clique real de mouse (mesma limitação dos botões de
            # wizard). Seguro aqui: o popup está comprovadamente na tela e a
            # bloqueia, então o 'Cancelar' visível é o dele.
            self.clica_real("cancelar")
        time.sleep(5)
        return True

    def fecha_dialogos(self, tentativas=4):
        """Fecha popups conhecidos (Reforma Tributária, erro do WebAgent,
        'Autorização do superior'...)."""
        fechou = []
        for _ in range(tentativas):
            algum = False
            if self.cancela_autorizacao_superior():
                fechou.append("Cancelar (Autorização do superior)")
                algum = True
            for botao in ("Ok", "Fechar"):
                if self.clica_caption(botao, exato=True):
                    fechou.append(botao)
                    algum = True
                    time.sleep(2)
            if not algum:
                break
        return fechou

    # ------------------------------------------------------ campos do SmartClient
    def _mapa(self):
        self._no_principal()
        return self._js(JS_MAPA_CAMPOS)

    def _indice_campo_do_label(self, mapa, label, tipos=("tget",), dx=80, dy=(5, 40)):
        """Índice do campo cujo label (texto exato) está logo acima/à esquerda."""
        alvo = label.strip().lower()
        candidatos = [l for l in mapa["labels"] if l["texto"].strip().lower() == alvo]
        if not candidatos:
            return None
        melhor, melhor_dist = None, None
        for lb in candidatos:
            for i, c in enumerate(mapa["campos"]):
                if c["advpl"] not in tipos:
                    continue
                dif_y = c["y"] - lb["y"]
                dif_x = abs(c["x"] - lb["x"])
                if dy[0] <= dif_y <= dy[1] and dif_x <= dx:
                    dist = dif_y + dif_x
                    if melhor_dist is None or dist < melhor_dist:
                        melhor, melhor_dist = i, dist
        return melhor

    def campo(self, label, tipos=("tget",), interno=True):
        """
        Elemento do campo identificado pelo label visível.
        interno=True devolve o <input> de dentro do shadow DOM (é o que aceita
        foco e digitação); interno=False devolve o host wa-* (útil para ler
        atributos como 'checked').
        """
        mapa = self._mapa()
        idx = self._indice_campo_do_label(mapa, label, tipos)
        if idx is None:
            raise RuntimeError(f"Campo do label {label!r} não encontrado na tela.")
        return self._js(JS_CAMPO_INTERNO if interno else JS_CAMPO_POR_INDICE, idx)

    def campo_existe(self, label, tipos=("tget",)):
        mapa = self._mapa()
        return self._indice_campo_do_label(mapa, label, tipos) is not None

    def preenche(self, label, valor, tipos=("tget",)):
        """
        Preenche um campo do SmartClient.
        ATENÇÃO: nos componentes wa-text-input o Ctrl+A NÃO seleciona o texto —
        ele DIGITA a letra "a" no campo (bug real observado em 29/07/2026, que
        gerava valores errados). A limpeza tem de ser feita com END + BACKSPACE.
        """
        valor = str(valor)
        ultimo = None

        # um popup de validação aberto bloqueia a tela — resolver antes
        problema = self.fecha_popup_ajuda()
        if problema:
            raise RuntimeError(f"Protheus reclamou antes de {label!r}: {problema}")

        for tentativa in range(3):
            el = self.campo(label, tipos)
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            self.driver.execute_script("arguments[0].focus();", el)
            try:
                el.click()
            except Exception:
                pass
            self._limpa(el)
            el.send_keys(valor)
            time.sleep(0.4)

            ultimo = (self.driver.execute_script("return arguments[0].value;", el) or "").strip()
            if self._conferido(ultimo, valor, el):
                return el

            problema = self.fecha_popup_ajuda()
            if problema:
                raise RuntimeError(f"Protheus recusou {label!r}: {problema}")
            self.log(f"    campo {label!r}: ficou {ultimo!r} em vez de {valor!r}"
                     f" (tentativa {tentativa + 1})")
        raise RuntimeError(
            f"Não consegui preencher {label!r}: ficou {ultimo!r} em vez de {valor!r}.")

    def define_login(self, candidatos, max_tentativas=15):
        """
        Escolhe o login digitando os candidatos no campo Usuário até um passar.

        O Protheus avisa **ao sair do campo** ("Não é permitido duplicação de
        códigos"), então é nesse momento que trocamos de candidato — é assim que
        a regra PRIMEIRO.ULTIMO -> PRIMEIRO.PENULTIMO -> ... -> PRIMEIRO.ULTIMO2
        funciona de fato.

        Não dá para decidir antes olhando a lista: depois de criar alguém o
        browse fica posicionado só naquele registro, e a busca da rotina filtra
        por outra coluna — a checagem prévia daria "livre" para login existente.

        Devolve o login aceito.
        """
        tentados = []
        for i, login in enumerate(candidatos):
            if i >= max_tentativas:
                break
            tentados.append(login)

            if not self.focar_campo("Usuário"):
                raise RuntimeError("Não consegui pôr o foco no campo 'Usuário'.")
            ativo = self.driver.switch_to.active_element
            atual = self.driver.execute_script("return arguments[0].value || '';", ativo)
            if atual.strip():
                ativo.send_keys(Keys.END)
                for _ in range(len(atual)):
                    ativo.send_keys(Keys.BACK_SPACE)
            ativo.send_keys(login)
            time.sleep(0.5)
            ativo.send_keys(Keys.TAB)
            time.sleep(2.5)

            if self.tem_texto("duplica"):
                self.fecha_popup_ajuda()
                self.fecha_popup_com_texto("duplica")
                time.sleep(1)
                self.log(f"    login '{login}' já existe — tentando o próximo")
                continue

            problema = self.fecha_popup_ajuda()
            if problema:
                raise RuntimeError(f"Protheus recusou o login {login!r}: {problema}")

            lido = self.valor_do_campo("Usuário")
            if lido != login:
                raise RuntimeError(f"O campo Usuário ficou {lido!r} em vez de {login!r}.")
            self.log(f"    login: {login}")
            return login

        raise RuntimeError(
            f"Nenhum login livre em {len(tentados)} tentativas: {', '.join(tentados)}")

    def focar_campo(self, label, tipos=("tget",), max_tabs=30):
        """
        Põe o foco NO campo pedido e CONFERE que chegou lá.

        Não dá para clicar e presumir: o clique no host pode focar o campo
        VIZINHO — bug real observado, em que o login foi digitado em 'Nome
        completo' e ainda por cima perdeu o primeiro caractere
        ('CAUA.GOSTEINSKI' virou 'AUA.GOSTEINSKI' no campo errado). E depois do
        'Incluir' o foco fica no BOTÃO, não no primeiro campo.

        Estratégia: andar com TAB comparando o elemento ativo com o host do
        campo alvo (o Protheus deixa o foco no host wa-text-input), até bater.
        """
        alvo = self.campo(label, tipos, interno=False)
        for _ in range(max_tabs):
            ativo = self.driver.switch_to.active_element
            if ativo == alvo:
                return True
            try:
                ativo.send_keys(Keys.TAB)
            except Exception:
                self.driver.execute_script("arguments[0].focus();", alvo)
            time.sleep(0.25)
        return self.driver.switch_to.active_element == alvo

    def preenche_por_tab(self, valores):
        """
        Preenche uma sequência de campos: para cada um, foca conferindo
        (`focar_campo`), digita no elemento ativo e confere o que ficou.

        Por que digitar no elemento ativo: mandar send_keys para o <input> de
        dentro do shadow DOM não escreve nada — o SmartClient só aceita
        digitação no campo que ele mesmo focou.

        `valores` é uma lista de (label, valor). Levanta erro no primeiro campo
        que não ficar como esperado, ANTES de qualquer gravação.
        """
        problema = self.fecha_popup_ajuda()
        if problema:
            raise RuntimeError(f"Popup de validação aberto antes de começar: {problema}")

        for label, valor in valores:
            valor = str(valor)
            if not self.focar_campo(label):
                raise RuntimeError(f"Não consegui pôr o foco no campo {label!r}.")

            ativo = self.driver.switch_to.active_element
            atual = self.driver.execute_script("return arguments[0].value || '';", ativo)
            # limpar também conteúdo SÓ de espaços: o form de vendedor vem com
            # um buffer de 40 espaços no campo, e o strip() aqui deixava os
            # espaços na frente ("Retire o espaço em branco da 1ª posição")
            if atual:
                ativo.send_keys(Keys.END)
                for _ in range(len(atual)):
                    ativo.send_keys(Keys.BACK_SPACE)
            ativo.send_keys(valor)
            time.sleep(0.5)

            lido = self.valor_do_campo(label)
            if not self._conferido(lido, valor, self.campo(label)):
                msg = self.fecha_popup_ajuda()
                raise RuntimeError(
                    f"Campo {label!r} ficou {lido!r} em vez de {valor!r}"
                    + (f" — Protheus disse: {msg}" if msg else ""))
            self.log(f"    {label}: {lido!r}")

            msg = self.fecha_popup_ajuda()
            if msg:
                raise RuntimeError(f"Protheus reclamou em {label!r}: {msg}")
        return True

    def _conferido(self, lido, esperado, elemento):
        """
        Confere o que ficou no campo. Campos de senha são mascarados (o valor
        lido vem como '●●●●'), então neles só é possível conferir o TAMANHO.
        """
        esperado = esperado.strip()
        if lido == esperado:
            return True
        mascarado = bool(self.driver.execute_script(
            "return (arguments[0].type || '') === 'password';", elemento)) or \
            (lido and set(lido) <= {"●", "•", "*"})
        return bool(mascarado and len(lido) == len(esperado))

    def _limpa(self, elemento):
        """
        Limpa um campo do SmartClient apagando EXATAMENTE o número de
        caracteres que existem.

        Duas armadilhas, as duas já custaram bug:
          * rajada de BACKSPACE em campo VAZIO manda o foco para o campo
            anterior e o texto seguinte vai para o lugar errado -> por isso
            saímos sem fazer nada quando o campo já está vazio;
          * `setSelectionRange` "funciona" (não lança erro), mas o tget do
            Protheus ignora a seleção e a digitação NÃO substitui nada -> por
            isso não dá para confiar só nela.
        """
        atual = self.driver.execute_script("return arguments[0].value || '';", elemento)
        if not atual.strip():
            return
        self.driver.execute_script(
            "const el = arguments[0];"
            "try { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }"
            "catch (e) {}", elemento)
        elemento.send_keys(Keys.END)
        for _ in range(len(atual)):
            elemento.send_keys(Keys.BACK_SPACE)

    def valor_do_campo(self, label, tipos=("tget",)):
        el = self.campo(label, tipos)
        return (self.driver.execute_script("return arguments[0].value;", el) or "").strip()

    def checkbox(self, label, marcado):
        """
        Garante o estado de um tcheckbox identificado pelo texto ao lado.
        Devolve o estado final REAL (confere depois de clicar).
        """
        mapa = self._mapa()
        idx = self._indice_campo_do_label(
            mapa, label, tipos=("tcheckbox",), dx=400, dy=(-15, 15))
        if idx is None:
            raise RuntimeError(f"Checkbox {label!r} não encontrado.")
        host = self._js(JS_CAMPO_POR_INDICE, idx)
        interno = self._js(JS_CAMPO_INTERNO, idx)

        def estado():
            # O <input> DENTRO do shadow DOM é só renderização: seu .checked
            # fica preso no valor inicial e NUNCA muda. O estado real é o do
            # host wa-checkbox (propriedade .checked / atributo 'checked').
            return bool(self.driver.execute_script(
                "const h = arguments[0];"
                "return h.checked === true || h.hasAttribute('checked');", host))

        # Alternar um tcheckbox: o clique no <input> interno não sensibiliza o
        # SmartClient. O que funciona é clicar no HOST wa-* ou dar ESPAÇO no
        # campo com foco (mesmo motivo dos campos de texto).
        def tenta_clique_real():
            # ActionChains gera um clique de mouse de verdade — é o ÚNICO jeito
            # que o SmartClient reconhece. Cliques sintéticos (element.click()
            # ou JS) não alternam o componente, e mexer na propriedade à mão
            # dessincroniza host e renderização.
            from selenium.webdriver.common.action_chains import ActionChains
            alvo = interno if interno is not None else host
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alvo)
            time.sleep(0.4)
            ActionChains(self.driver).move_to_element(alvo).pause(0.2).click().perform()

        def tenta_host():
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", host)
            try:
                host.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", host)

        def tenta_espaco():
            self.driver.execute_script("arguments[0].focus();", host)
            try:
                self.driver.switch_to.active_element.send_keys(Keys.SPACE)
            except Exception:
                pass

        def tenta_interno():
            if interno is None:
                return
            try:
                interno.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", interno)

        for estrategia in (tenta_clique_real, tenta_clique_real,
                           tenta_host, tenta_espaco, tenta_interno):
            if estado() == bool(marcado):
                return bool(marcado)
            estrategia()
            time.sleep(0.9)
        final = estado()
        if final != bool(marcado):
            raise RuntimeError(
                f"Checkbox {label!r} ficou {final} (esperado {bool(marcado)}).")
        return final

    # ---------------------------------------------------------------- contexto
    def esta_no_login(self):
        if not self._no_iframe():
            return False
        try:
            return bool(self.driver.find_elements(By.CSS_SELECTOR, "input[name='login']"))
        finally:
            self._no_principal()

    def esta_na_selecao(self):
        if not self._no_iframe():
            return False
        try:
            return bool(self.driver.find_elements(
                By.CSS_SELECTOR, "pro-branch-lookup input.po-lookup-input"))
        finally:
            self._no_principal()

    def fazer_login(self, usuario, senha):
        """Só usado se a sessão NÃO estiver logada (tela de usuário/senha).
        Aqui os campos são <input> do Angular (PO-UI), onde .clear() funciona."""
        if not self._no_iframe():
            raise RuntimeError("Iframe de login não encontrado.")
        try:
            campo_user = self.driver.find_element(By.CSS_SELECTOR, "input[name='login']")
            campo_user.click()
            campo_user.clear()
            campo_user.send_keys(usuario)

            campo_pass = self.driver.find_element(By.CSS_SELECTOR, "input[name='password']")
            campo_pass.click()
            campo_pass.clear()
            campo_pass.send_keys(senha)

            self._clica_po_botao("Entrar")
            time.sleep(6)

            if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'não autenticado')]"):
                raise RuntimeError("Usuário não autenticado (login/senha do Protheus).")
        finally:
            self._no_principal()

    def _clica_po_botao(self, texto):
        for b in self.driver.find_elements(By.CSS_SELECTOR, "button"):
            if (b.text or "").strip().lower() == texto.lower():
                b.click()
                return True
        return False

    def selecionar_contexto_po(self, grupo, filial_codigo, ambiente):
        """Tela de seleção do PO-UI (iframe): Grupo / Filial / Ambiente -> Entrar."""
        if not self._no_iframe():
            raise RuntimeError("Tela de seleção (iframe) não encontrada.")
        try:
            self._po_preenche("pro-company-lookup input.po-lookup-input", grupo)
            self._po_preenche("pro-branch-lookup input.po-lookup-input", filial_codigo)
            time.sleep(2)
            desc = self.driver.find_element(
                By.CSS_SELECTOR, "input[name='branch_description']").get_attribute("value")
            if not (desc or "").strip():
                raise FilialInvalida(filial_codigo)
            self._po_preenche("pro-system-module-lookup input.po-lookup-input", ambiente)
            time.sleep(2)
            self._clica_po_botao("Entrar")
        finally:
            self._no_principal()
        time.sleep(30)
        self.fecha_dialogos()

    def _po_preenche(self, css, valor):
        el = self.driver.find_element(By.CSS_SELECTOR, css)
        el.click()
        el.clear()
        el.send_keys(str(valor))
        el.send_keys(Keys.TAB)
        time.sleep(1.5)

    def no_dialogo_contexto(self):
        """
        A janelinha de contexto está aberta?
        NÃO usar tem_texto('TOTVS Linha Protheus'): a tela de carregamento
        mostra 'Aguarde para utilizar o TOTVS Linha Protheus' e dá falso
        positivo. O sinal confiável é o label 'Data base*' com um campo.
        """
        self._no_principal()
        campos = self._js(JS_CAMPOS_CONTEXTO)
        return bool(campos) and len(campos) >= 6

    def trocar_modulo(self, grupo, filial_codigo, ambiente):
        """Janelinha 'TOTVS Linha Protheus.' (SmartClient) — troca de filial."""
        self.fecha_dialogos()
        if not self.no_dialogo_contexto():
            if not self.clica_caption("Trocar módulo", exato=True):
                raise RuntimeError("Botão 'Trocar módulo' não encontrado.")
            time.sleep(5)
            if not self.no_dialogo_contexto():
                raise RuntimeError("A janelinha de contexto não abriu.")

        # Atalho: o diálogo pode JÁ estar aberto com os valores certos (ex.:
        # contexto re-pedido ao abrir uma rotina, sobra de tentativa anterior).
        # Nesse estado os campos podem vir BLOQUEADOS — digitar neles dá
        # "element not interactable" (aconteceu no mapeamento de Vendedores,
        # 31/07/2026). Se filial e ambiente já são os pedidos, só confirma.
        try:
            if (self._contexto_valor(self.IDX_FILIAL) == str(filial_codigo)
                    and self._contexto_valor(self.IDX_AMBIENTE) == str(ambiente)):
                self.log("  contexto já está com os valores certos — só confirmando")
                desc = self._contexto_valor(self.IDX_FILIAL_DESC)
                if desc:
                    self.ultima_filial_nome = desc
                if not self.clica_caption("Confirmar", exato=True):
                    raise RuntimeError("Botão 'Confirmar' do contexto não encontrado.")
                # esse diálogo pode ser o contexto RE-PEDIDO por uma rotina:
                # confirmar abre a ROTINA direto, e aí 'Trocar módulo' nem
                # existe — aceitar também uma aba de rotina como sucesso
                fim = time.time() + 180
                while time.time() < fim:
                    self.fecha_dialogos(tentativas=1)
                    if self._js(JS_TEM_TROCAR_MODULO) or self._js(JS_TEM_ABA_ROTINA):
                        time.sleep(2)
                        return
                    time.sleep(3)
                raise RuntimeError(
                    "Depois de confirmar o contexto a tela não carregou.")
        except RuntimeError:
            raise
        except Exception as e:
            self.log(f"  (atalho do contexto falhou, seguindo o caminho normal: {e})")

        # os campos do diálogo, na ordem: 1 Data base, 2 Grupo, 4 Filial, 6 Ambiente
        self._dialogo_contexto_preenche(grupo, filial_codigo, ambiente)
        if not self.clica_caption("Confirmar", exato=True):
            raise RuntimeError("Botão 'Confirmar' do contexto não encontrado.")
        self.esperar_modulo_pronto()

    def esperar_modulo_pronto(self, limite=180):
        """
        Espera o módulo terminar de carregar depois do Confirmar. Em vez de um
        sleep fixo, aguarda o sinal real: o menu lateral (botão 'Trocar módulo')
        ficar disponível. Fecha os popups que aparecem no caminho.
        """
        fim = time.time() + limite
        while time.time() < fim:
            self.fecha_dialogos(tentativas=1)
            if self._js(JS_TEM_TROCAR_MODULO):
                time.sleep(2)
                self.fecha_dialogos(tentativas=1)
                return True
            time.sleep(3)
        raise RuntimeError(
            f"O módulo não terminou de carregar em {limite}s (menu não apareceu).")

    # ------------------------------------- diálogo de contexto por POSIÇÃO
    # Nesse diálogo o casamento label->campo é frágil (o diálogo se reposiciona
    # e o label 'Ambiente*' chega a alinhar com o campo do Grupo, gravando no
    # lugar errado). A ordem visual dos campos, porém, é fixa:
    #   0 Data base | 1 Grupo cód | 2 Grupo desc | 3 Filial cód | 4 Filial desc
    #   5 Ambiente cód | 6 Ambiente desc | 7 Papel cód | 8 Papel desc
    IDX_GRUPO, IDX_GRUPO_DESC = 1, 2
    IDX_FILIAL, IDX_FILIAL_DESC = 3, 4
    IDX_AMBIENTE, IDX_AMBIENTE_DESC = 5, 6

    def _campos_contexto(self):
        self._no_principal()
        campos = self._js(JS_CAMPOS_CONTEXTO)
        if campos is None:
            raise RuntimeError("Diálogo de contexto não encontrado na tela.")
        return campos

    def _contexto_elemento(self, posicao):
        campos = self._campos_contexto()
        if posicao >= len(campos):
            raise RuntimeError(
                f"Diálogo de contexto com poucos campos ({len(campos)}); "
                f"esperava pelo menos {posicao + 1}.")
        return self._js(JS_CTX_POR_INDICE, posicao)

    def _contexto_valor(self, posicao):
        self._campos_contexto()          # repopula window.__ac_ctx
        valor = self._js(JS_CTX_VALOR, posicao)
        return (valor or "").strip()

    def _contexto_escreve(self, posicao, valor):
        """
        Escreve num campo da janela de contexto. Aqui o alvo é o HOST
        wa-text-input (ver comentário de JS_CTX_POR_INDICE) e a limpeza é por
        BACKSPACE contado — o campo sempre tem conteúdo, então não há risco de
        o foco pular para o campo anterior.
        """
        el = self._contexto_elemento(posicao)
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].focus();", el)
        time.sleep(0.4)

        atual = self._contexto_valor(posicao)
        el = self._contexto_elemento(posicao)
        for _ in range(max(len(atual), 12) + 4):
            el.send_keys(Keys.BACK_SPACE)
        el.send_keys(Keys.DELETE)
        el.send_keys(str(valor))
        el.send_keys(Keys.TAB)
        time.sleep(2.5)

    def _dialogo_contexto_preenche(self, grupo, filial_codigo, ambiente):
        self._contexto_escreve(self.IDX_GRUPO, grupo)

        # guarda a descrição ANTES de trocar: ela demora a atualizar e, se
        # lermos cedo, pegamos a descrição da filial anterior (já aconteceu:
        # 01DOMA0001 aparecendo como "AUTO POSTO PETRO TRIANGULO LTDA").
        desc_antes = self._contexto_valor(self.IDX_FILIAL_DESC)
        self._contexto_escreve(self.IDX_FILIAL, filial_codigo)

        desc = ""
        for _ in range(8):
            desc = self._contexto_valor(self.IDX_FILIAL_DESC)
            codigo_ok = self._contexto_valor(self.IDX_FILIAL) == str(filial_codigo)
            if codigo_ok and desc and desc != desc_antes:
                break
            time.sleep(1.5)
        if not desc:
            raise FilialInvalida(filial_codigo)
        if desc == desc_antes:
            self.log(f"  aviso: a descrição da filial não mudou ({desc!r}) — "
                     f"confirmando pelo código {filial_codigo}")
        self.log(f"  filial {filial_codigo} = {desc}")
        # guarda a descrição lida: o chamador usa para alimentar o filiais.json
        self.ultima_filial_nome = desc

        self._contexto_escreve(self.IDX_AMBIENTE, ambiente)
        amb_desc = self._contexto_valor(self.IDX_AMBIENTE_DESC)
        self.log(f"  ambiente {ambiente} = {amb_desc}")

        # confere o que realmente ficou gravado nos campos
        gravado = {
            "grupo": self._contexto_valor(self.IDX_GRUPO),
            "filial": self._contexto_valor(self.IDX_FILIAL),
            "ambiente": self._contexto_valor(self.IDX_AMBIENTE),
        }
        esperado = {"grupo": str(grupo), "filial": str(filial_codigo),
                    "ambiente": str(ambiente)}
        if gravado != esperado:
            # Se o código da filial não "pegou", o Protheus recusou o valor —
            # trata como filial inválida (é o caso de código inexistente, em
            # que o Protheus abre a consulta e descarta o que foi digitado).
            if gravado["filial"] != str(filial_codigo):
                raise FilialInvalida(filial_codigo)
            raise RuntimeError(
                f"O contexto não ficou como esperado: {gravado} != {esperado}")

    # --------------------------------------------------- cadastro de usuários
    def abrir_cadastro_usuarios(self):
        """Miscelanea (18) -> Usuários. Se a aba já existir, só foca nela."""
        self.fecha_dialogos()
        if self.clica_caption("Usuários [", exato=False):
            time.sleep(3)
            if self.tem_texto("Cadastro de usuários"):
                return True
        # o submenu do Miscelanea renderiza com atraso depois de trocar de
        # filial, então tenta algumas vezes antes de desistir
        achou_item = False
        for tentativa in range(6):
            if not self.clica_caption("miscelanea", exato=False):
                raise RuntimeError("Menu 'Miscelanea' não encontrado.")
            time.sleep(3 + tentativa)
            if self.clica_caption("Usuários", exato=True):
                achou_item = True
                break
            self.log(f"  submenu ainda não carregou (tentativa {tentativa + 1})")
        if not achou_item:
            raise RuntimeError("Item de menu 'Usuários' não encontrado.")

        # Espera a rotina abrir. Atenção: ao abrir a rotina o Protheus pode
        # pedir o contexto DE NOVO (janelinha 'TOTVS Linha Protheus.') — nesse
        # caso é só confirmar, pois os valores já estão certos.
        fim = time.time() + 180
        while time.time() < fim:
            self.fecha_dialogos(tentativas=1)
            if self.tem_texto("Cadastro de usuários"):
                time.sleep(2)
                return True
            if self.no_dialogo_contexto():
                self.log("  o Protheus pediu o contexto novamente — confirmando")
                self.clica_caption("Confirmar", exato=True)
                time.sleep(10)
                continue
            time.sleep(3)
        raise RuntimeError("Tela 'Cadastro de usuários' não abriu.")

    JS_CAMPO_PESQUISA = r"""
    // campo "Pesquisar" da rotina (tget com esse placeholder), visível
    let achado = null;
    function varre(raiz) {
      for (const el of raiz.querySelectorAll('[data-advpl="tget"]')) {
        if ((el.getAttribute('placeholder') || '') === 'Pesquisar') {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) { achado = el; return true; }
        }
        if (el.shadowRoot && varre(el.shadowRoot)) return true;
      }
      for (const el of raiz.querySelectorAll('*')) {
        if (el.shadowRoot && varre(el.shadowRoot)) return true;
      }
      return false;
    }
    varre(document);
    return achado;
    """

    def usuario_existe(self, login):
        """
        Diz se o login já existe, PESQUISANDO na rotina.

        Não basta procurar o texto na tela: depois de criar alguém a lista fica
        posicionada só naquele registro, então uma busca visual daria "não
        existe" para logins que existem — e a regra de login alternativo
        (PRIMEIRO.PENULTIMO, ...2, ...) deixaria de funcionar.
        """
        login = (login or "").strip()
        if not login:
            return False
        encontrado = self._pesquisa_na_lista(login)
        if encontrado is None:                 # sem campo de busca: cai no visual
            return bool(self.tem_texto(login.lower()))
        return encontrado

    def _pesquisa_na_lista(self, texto):
        """
        Digita `texto` no campo Pesquisar da rotina e diz se apareceu alguma
        linha com ele. Limpa a busca no fim, para não deixar a lista filtrada.
        Devolve None se não houver campo de busca na tela.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        self._no_principal()
        campo = self._js(self.JS_CAMPO_PESQUISA)
        if campo is None:
            return None
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", campo)
            ActionChains(self.driver).move_to_element(campo).pause(0.2).click().perform()
            time.sleep(0.5)
            ativo = self.driver.switch_to.active_element
            atual = self.driver.execute_script("return arguments[0].value || '';", ativo)
            if atual.strip():
                ativo.send_keys(Keys.END)
                for _ in range(len(atual)):
                    ativo.send_keys(Keys.BACK_SPACE)
            ativo.send_keys(texto)
            ativo.send_keys(Keys.RETURN)
            time.sleep(2.5)
            achou = bool(self.tem_texto(texto.lower()))

            # limpa a busca para a lista voltar ao normal
            try:
                ativo = self.driver.switch_to.active_element
                ativo.send_keys(Keys.END)
                for _ in range(len(texto) + 4):
                    ativo.send_keys(Keys.BACK_SPACE)
                ativo.send_keys(Keys.RETURN)
                time.sleep(1.5)
            except Exception:
                pass
            return achou
        except Exception as e:
            self.log(f"    aviso: pesquisa por {texto!r} falhou ({e})")
            return None

    JS_SELECIONA_COMBO = r"""
    // Combos são <select> dentro do shadow DOM: mexer no value + disparar
    // input/change funciona (ao contrário dos checkboxes).
    const alvo = arguments[0].toLowerCase();
    let res = null;
    function varre(raiz) {
      for (const el of raiz.querySelectorAll('*')) {
        if (el.getAttribute && el.getAttribute('data-advpl') === 'tcombobox') {
          const sel = (el.shadowRoot && el.shadowRoot.querySelector('select')) || el.querySelector('select');
          if (sel) {
            const op = Array.from(sel.options).find(o => o.text.trim().toLowerCase().includes(alvo));
            if (op) {
              sel.focus();
              sel.value = op.value;
              sel.dispatchEvent(new Event('input', {bubbles: true}));
              sel.dispatchEvent(new Event('change', {bubbles: true}));
              res = op.text.trim();
              return true;
            }
          }
        }
        if (el.shadowRoot && varre(el.shadowRoot)) return true;
      }
      return false;
    }
    varre(document);
    return res;
    """

    def seleciona_combo(self, texto_opcao):
        """Escolhe a opção do combo cujo texto contém `texto_opcao`."""
        self._no_principal()
        return self._js(self.JS_SELECIONA_COMBO, texto_opcao)

    JS_ABA_POR_TEXTO = r"""
    // wa-tab-button cujo texto é exatamente o pedido
    const alvo = arguments[0];
    let achado = null;
    function varre(raiz) {
      for (const el of raiz.querySelectorAll('wa-tab-button')) {
        if ((el.textContent || '').replace(/\s+/g, ' ').trim() === alvo) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) { achado = el; return true; }
        }
        if (el.shadowRoot && varre(el.shadowRoot)) return true;
      }
      for (const el of raiz.querySelectorAll('*')) {
        if (el.shadowRoot && varre(el.shadowRoot)) return true;
      }
      return false;
    }
    varre(document);
    return achado;
    """

    def clica_aba(self, nome, texto_esperado=None, tentativas=3):
        """
        Ativa uma sub-aba (wa-tab-button) com clique REAL de mouse.

        Clique sintético NÃO troca de aba: ele "funciona" (não dá erro) mas a
        aba ativa continua a mesma — o sintoma é o conteúdo da aba pedida ficar
        com largura 0 (bug real: a grade de Grupos nunca aparecia porque a aba
        ativa seguia 'Superior').

        Se `texto_esperado` for informado, confere que aquele conteúdo passou a
        estar visível de fato.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        for _ in range(tentativas):
            self._no_principal()
            aba = self._js(self.JS_ABA_POR_TEXTO, nome)
            if aba is None:
                raise RuntimeError(f"Sub-aba {nome!r} não encontrada.")
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", aba)
            time.sleep(0.3)
            try:
                ActionChains(self.driver).move_to_element(aba).pause(0.2).click().perform()
            except Exception as e:
                self.log(f"    clique na aba {nome!r} falhou: {e}")
            time.sleep(2.5)

            if texto_esperado is None:
                return True
            cels = self._js(JS_CELULAS_GRADE_GRUPOS)
            if any(c["t"] == texto_esperado for c in cels):
                return True
            self.log(f"    aba {nome!r} clicada mas {texto_esperado!r} não apareceu; repetindo")
        return False

    def preenche_grupo(self, grupo_codigo, prioriza=True):
        """
        Preenche a grade da sub-aba Grupos: código do grupo e Prioriza = Sim.
        A grade não expõe campos localizáveis por label — é preciso clicar na
        célula por coordenada (clique real) e digitar no campo que o Protheus
        abrir para edição.
        """
        if not self.clica_aba("Grupos", texto_esperado="Grupo"):
            raise RuntimeError("Não consegui ativar a sub-aba 'Grupos'.")
        time.sleep(1.5)

        cels = self._js(JS_CELULAS_GRADE_GRUPOS)
        # cabeçalho da grade: texto exatamente 'Grupo' (não 'Grupos', que é a
        # aba, nem 'Regra de acesso por grupo'), encostado na esquerda.
        cabecalhos = [c for c in cels if c["t"] == "Grupo" and c["x"] < 60]
        if not cabecalhos:
            vizinhos = [c["t"] for c in cels if "grupo" in c["t"].lower()][:8]
            raise RuntimeError(
                "Cabeçalho 'Grupo' da grade não encontrado. "
                f"Textos com 'grupo' na tela: {vizinhos}")
        # se houver mais de um, o da grade é o mais abaixo
        cab = max(cabecalhos, key=lambda c: c["y"])
        self.log(f"    cabeçalho da grade em y={cab['y']}")

        # célula da 1ª linha, coluna Grupo (logo abaixo do cabeçalho)
        if not self._clica_celula(cab["x"] + 30, cab["y"] + 28, grupo_codigo, com_tab=True):
            raise RuntimeError(f"Não consegui informar o grupo {grupo_codigo} na grade.")
        time.sleep(2)

        # confere que o grupo entrou (o Protheus resolve o nome ao lado).
        # Atenção: a lista de usuários por trás também mostra códigos de 6
        # dígitos na coluna Id — por isso exigimos que a linha esteja ABAIXO do
        # cabeçalho da grade.
        # ⚠️ A resolução do nome pode DEMORAR e a digitação pode não pegar na
        # primeira (célula sem foco) — checagem única derrubou a REGINA na
        # execução 16 ("O grupo 000013 não apareceu na grade") sem motivo.
        # Agora: espera até 8s e REDIGITA até 2 vezes antes de desistir.
        linha = None
        for tentativa in range(3):
            fim = time.time() + 8
            while time.time() < fim:
                cels = self._js(JS_CELULAS_GRADE_GRUPOS)
                linha = next((c for c in cels if c["t"] == str(grupo_codigo)
                              and c["x"] < 60 and c["y"] > cab["y"]), None)
                if linha:
                    break
                time.sleep(1)
            if linha:
                break
            self.log(f"    grupo ainda não apareceu na grade "
                     f"(tentativa {tentativa + 1}) — digitando de novo")
            if not self._clica_celula(cab["x"] + 30, cab["y"] + 28,
                                      grupo_codigo, com_tab=True):
                raise RuntimeError(
                    f"Não consegui informar o grupo {grupo_codigo} na grade.")
            time.sleep(2)
        if not linha:
            raise RuntimeError(f"O grupo {grupo_codigo} não apareceu na grade.")
        cels = self._js(JS_CELULAS_GRADE_GRUPOS)
        nome = next((c["t"] for c in cels
                     if abs(c["y"] - linha["y"]) < 8 and 60 < c["x"] < 400), "")
        self.log(f"    grupo na grade: {grupo_codigo} {nome}")

        if not prioriza:
            return True

        # Prioriza: célula da mesma linha, à direita do nome
        pri = next((c for c in cels if abs(c["y"] - linha["y"]) < 10
                    and c["t"] in ("Não", "Sim") and 300 < c["x"] < 700), None)
        if pri is None:
            self.log("    aviso: célula Prioriza não localizada.")
            return False
        if pri["t"] == "Sim":
            return True
        # 1 = Sim na convenção do Protheus
        self._clica_celula(pri["cx"], pri["cy"], "1", com_enter=True)
        time.sleep(2)
        cels = self._js(JS_CELULAS_GRADE_GRUPOS)
        pri2 = next((c for c in cels if abs(c["y"] - linha["y"]) < 10
                     and c["t"] in ("Não", "Sim") and 300 < c["x"] < 700), None)
        valor = pri2["t"] if pri2 else "?"
        self.log(f"    Prioriza = {valor}")
        return valor == "Sim"

    def _clica_celula(self, x, y, valor, com_tab=False, com_enter=False):
        """Clique real numa célula da grade e digita `valor` no editor."""
        from selenium.webdriver.common.action_chains import ActionChains
        el = self._js(JS_ELEMENTO_NO_PONTO, x, y)
        if el is None:
            return False
        try:
            ActionChains(self.driver).move_to_element(el).pause(0.3).click().perform()
        except Exception as e:
            self.log(f"    clique na célula ({x},{y}) falhou: {e}")
            return False
        time.sleep(2)
        try:
            ativo = self.driver.switch_to.active_element
            ativo.send_keys(str(valor))
            time.sleep(0.8)
            if com_tab:
                self.driver.switch_to.active_element.send_keys(Keys.TAB)
            if com_enter:
                self.driver.switch_to.active_element.send_keys(Keys.RETURN)
            return True
        except Exception as e:
            self.log(f"    digitação na célula falhou: {e}")
            return False

    def clica_real(self, trecho_texto):
        """
        Clica um botão pelo texto PARCIAL usando clique REAL de mouse.
        Necessário para os botões do wizard ("Avançar >>", "Finalizar"): o
        clique sintético do Selenium não os aciona (mesma limitação dos
        checkboxes). Os textos vêm fragmentados pelo accesskey ("vançar >> A"),
        por isso a comparação é parcial.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        self._no_principal()
        el = self._js(JS_BOTAO_POR_TEXTO_PARCIAL, trecho_texto.lower())
        if el is None:
            return None
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.3)
            ActionChains(self.driver).move_to_element(el).pause(0.2).click().perform()
            return True
        except Exception as e:
            self.log(f"    clique real em {trecho_texto!r} falhou: {e}")
            return False

    JS_TEXTO_DIALOGO_TOPO = r"""
    // Texto do wa-dialog VISÍVEL de menor área (= o modal do topo). Usado para
    // detectar a troca de etapa do wizard sem esperas fixas.
    function texto(raiz) {
      let out = ''; const pilha = [raiz]; const vistos = new Set();
      while (pilha.length) {
        const no = pilha.pop();
        if (!no || vistos.has(no)) continue;
        vistos.add(no);
        for (const f of (no.childNodes || [])) {
          if (f.nodeType === 3) out += ' ' + f.textContent; else pilha.push(f);
        }
        if (no.shadowRoot) pilha.push(no.shadowRoot);
      }
      return out.replace(/\s+/g, ' ').trim();
    }
    const cands = [];
    function coleta(raiz) {
      for (const el of raiz.querySelectorAll('wa-dialog')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) cands.push({el, area: r.width * r.height});
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
      for (const el of raiz.querySelectorAll('*')) { if (el.shadowRoot) coleta(el.shadowRoot); }
    }
    coleta(document);
    if (!cands.length) return '';
    cands.sort((a, b) => a.area - b.area);
    return texto(cands[0].el).substring(0, 1200);
    """

    def _texto_dialogo_topo(self):
        self._no_principal()
        return self._js(self.JS_TEXTO_DIALOGO_TOPO) or ""

    def _espera_dialogo_mudar(self, antes, teto):
        """
        Espera a etapa do wizard trocar (o texto do diálogo do topo mudar),
        checando a cada 0.3s até `teto` segundos. Substitui as esperas fixas
        de 4s/7s por etapa (pedido do usuário em 30/07/2026 — o wizard estava
        lento demais); no pior caso equivale à espera fixa antiga.
        """
        fim = time.time() + teto
        while time.time() < fim:
            time.sleep(0.3)
            if self._texto_dialogo_topo() != antes:
                time.sleep(0.4)   # respiro para a etapa terminar de renderizar
                return True
        return False

    def percorrer_wizard_caixa(self, limite=25):
        """
        Percorre o wizard "Configuração do caixa" que aparece depois do
        Confirmar, aceitando todos os padrões: Avançar >> até o fim e então
        Finalizar. Devolve True quando aparece "Registro inserido com sucesso".
        Todas as etapas são só Avançar (valores padrão) e Finalizar no fim.
        """
        # ⚠️ FINALIZAR é testado ANTES de Avançar: na última etapa os DOIS
        # botões ficam visíveis (o Avançar aparece desabilitado, mas com
        # tamanho > 0) e o clique nele não faz nada. A ordem antiga
        # (Avançar primeiro + continue) ficava PRESA na última etapa,
        # queimando ~7s × 25 tentativas POR USUÁRIO — eram esses os 4-5 min
        # por usuário medidos na execução nº 10 (30/07/2026).
        # Não desistir na PRIMEIRA rodada sem botão: o wizard pode ainda estar
        # abrindo (o Protheus processa entre o popup do código e o wizard) —
        # na execução 11 o loop rodou cedo demais, não viu botão nenhum e
        # abandonou o wizard intocado. Só desiste após ~5 rodadas vazias.
        sucesso = False
        vazias = 0
        for _ in range(limite):
            antes = self._texto_dialogo_topo()
            if self.clica_real("finalizar") is True:
                vazias = 0
                self._espera_dialogo_mudar(antes, 10)
                continue
            if self.clica_real("avançar") is True:
                vazias = 0
                if not self._espera_dialogo_mudar(antes, 6):
                    self.log("    wizard: a etapa não mudou depois do Avançar")
                continue
            msg = self.fecha_popup_com_texto("sucesso")
            if msg:
                self.log(f"    {msg[:80]}")
                sucesso = True
                vazias = 0
                continue
            vazias += 1
            if sucesso or vazias >= 5:
                break
            time.sleep(3)
        return sucesso

    JS_CLICA_NO_DIALOGO = r"""
    // Clica um botão DENTRO do menor wa-dialog que contenha o trecho de texto.
    const trecho = arguments[0].toLowerCase();
    const rotulo = arguments[1].toLowerCase();
    function texto(raiz) {
      let out = ''; const pilha = [raiz]; const vistos = new Set();
      while (pilha.length) {
        const no = pilha.pop();
        if (!no || vistos.has(no)) continue;
        vistos.add(no);
        for (const f of (no.childNodes || [])) {
          if (f.nodeType === 3) out += ' ' + f.textContent; else pilha.push(f);
        }
        if (no.shadowRoot) pilha.push(no.shadowRoot);
      }
      return out.replace(/\s+/g, ' ').trim();
    }
    const cands = [];
    function coleta(raiz) {
      for (const el of raiz.querySelectorAll('wa-dialog')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && texto(el).toLowerCase().includes(trecho)) {
          cands.push({el, area: r.width * r.height});
        }
        if (el.shadowRoot) coleta(el.shadowRoot);
      }
      for (const el of raiz.querySelectorAll('*')) { if (el.shadowRoot) coleta(el.shadowRoot); }
    }
    coleta(document);
    if (!cands.length) return null;
    cands.sort((a, b) => a.area - b.area);
    const dlg = cands[0].el;
    let alvo = null;
    function acha(raiz) {
      for (const el of raiz.querySelectorAll('wa-button, button')) {
        const t = ((el.textContent || '') + ' ' +
                   ((el.getAttribute && el.getAttribute('caption')) || ''))
                  .replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
        if (t.includes(rotulo)) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) { alvo = el; return true; }
        }
        if (el.shadowRoot && acha(el.shadowRoot)) return true;
      }
      return false;
    }
    acha(dlg);
    if (dlg.shadowRoot) acha(dlg.shadowRoot);
    if (!alvo) return 'SEM_BOTAO';
    alvo.click();
    return 'ok';
    """

    def abandonar_formulario(self):
        """
        Fecha o formulário DESCARTANDO o que foi digitado.

        Ao fechar um formulário sujo o Protheus abre o modal "Há alterações não
        salvas no formulário!" com Continuar editando / Salvar / Sair da página.
        Esse modal BLOQUEIA a tela (o foco fica preso num botão e nada é
        digitado). Aqui respondemos **Sair da página** — nunca 'Salvar', que
        gravaria um usuário pela metade.
        """
        if not self.campo_existe("Confirme a senha"):
            return True

        for tentativa in range(3):
            self.fecha_popup_ajuda()
            self.clica_caption("Fechar", exato=True)

            # espera: ou o formulário fecha, ou aparece o modal de alterações
            for _ in range(10):
                time.sleep(1)
                if self.tem_texto("alterações não salvas"):
                    self._no_principal()
                    r = self._js(self.JS_CLICA_NO_DIALOGO,
                                 "alterações não salvas", "sair da página")
                    self.log(f"    descartando alterações do formulário ({r})")
                    time.sleep(4)
                    break
                if not self.campo_existe("Confirme a senha"):
                    return True

            if not self.campo_existe("Confirme a senha"):
                return True
            self.log(f"    formulário ainda aberto (tentativa {tentativa + 1})")

        self.fecha_dialogos()
        return not self.campo_existe("Confirme a senha")

    def fechar_rotina(self):
        """
        Fecha o formulário e a aba da rotina, voltando ao workspace com o menu
        lateral. É obrigatório antes de trocar de filial: enquanto a rotina
        está aberta, o botão 'Trocar módulo' nem existe no DOM.
        """
        # 1) formulário de inclusão/alteração aberto? descarta sem salvar
        self.abandonar_formulario()
        self.fecha_dialogos()

        # 2) fecha a aba da rotina (o X ao lado do título). O Protheus pergunta
        #    "O processo da sessao atual sera interrompido..." -> responder Sim.
        for _ in range(3):
            fechou = self._js(JS_FECHA_ABA_ROTINA)
            if not fechou:
                break
            time.sleep(3)
            self.confirma_interrupcao_sessao()
            time.sleep(4)
            self.fecha_dialogos()

        # 3) confirma que o menu voltou
        for _ in range(6):
            if self._js(JS_TEM_TROCAR_MODULO):
                return True
            time.sleep(2)
        return bool(self._js(JS_TEM_TROCAR_MODULO))


class FilialInvalida(Exception):
    """A filial informada não existe / não foi aceita pelo Protheus."""
