from __future__ import annotations

import tkinter as tk
from tkinter import ttk


_SCROLL_UNITS = 3
_PATCH_MARKER = "_odin_display_settings_ux_instalado"


def _percorrer_widgets(widget):
    yield widget
    try:
        filhos = tuple(widget.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        yield from _percorrer_widgets(filho)


def _texto_widget(widget) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _classe_widget(widget) -> str:
    try:
        return str(widget.winfo_class())
    except Exception:
        return type(widget).__name__


def _configurar(widget, **opcoes) -> None:
    try:
        widget.configure(**opcoes)
    except Exception:
        pass


def calcular_unidades_rolagem(evento, unidades: int = _SCROLL_UNITS) -> int:
    """Converte roda do Windows/macOS e botões 4/5 do Linux em unidades Tk."""
    numero = getattr(evento, "num", None)
    if numero == 4:
        return -abs(int(unidades))
    if numero == 5:
        return abs(int(unidades))

    delta = int(getattr(evento, "delta", 0) or 0)
    if delta == 0:
        return 0

    # Windows normalmente envia múltiplos de 120. Alguns touchpads/macOS
    # enviam deltas menores; nesses casos a direção continua previsível.
    passos = max(1, abs(delta) // 120)
    direcao = -1 if delta > 0 else 1
    return direcao * passos * abs(int(unidades))


def rolar_canvas(canvas, unidades: int) -> bool:
    """Rola um Canvas somente quando existe conteúdo naquela direção."""
    if canvas is None or int(unidades) == 0:
        return False

    try:
        inicio, fim = canvas.yview()
    except Exception:
        return False

    if unidades < 0 and inicio <= 0.0:
        return False
    if unidades > 0 and fim >= 1.0:
        return False

    try:
        canvas.yview_scroll(int(unidades), "units")
        return True
    except Exception:
        return False


def _encontrar_janela_configuracoes(root, janelas_antes=()):
    anteriores = set(janelas_antes or ())
    candidatas = []
    try:
        filhos = tuple(root.winfo_children())
    except Exception:
        filhos = ()

    for widget in filhos:
        if not isinstance(widget, tk.Toplevel):
            continue
        try:
            if not widget.winfo_exists():
                continue
            titulo = str(widget.title())
        except Exception:
            continue
        if titulo == "Configurações - ODIN":
            candidatas.append(widget)

    novas = [janela for janela in candidatas if janela not in anteriores]
    if novas:
        return novas[-1]
    return candidatas[-1] if candidatas else None


def _obter_notebook(janela):
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, ttk.Notebook):
            return widget
    return None


def _obter_canvases_rolagem(janela):
    canvases = []
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Canvas):
            continue
        try:
            comando = str(widget.cget("yscrollcommand") or "")
        except Exception:
            comando = ""
        if comando:
            canvases.append(widget)
    return canvases


def _canvas_ancestral(widget, canvases):
    conjunto = set(canvases)
    atual = widget
    while atual is not None:
        if atual in conjunto:
            return atual
        atual = getattr(atual, "master", None)
    return None


def _canvas_ativo(janela, canvases, evento=None):
    if evento is not None:
        try:
            sob_mouse = janela.winfo_containing(evento.x_root, evento.y_root)
        except Exception:
            sob_mouse = None
        encontrado = _canvas_ancestral(sob_mouse, canvases)
        if encontrado is not None:
            return encontrado

    for canvas in canvases:
        try:
            if canvas.winfo_ismapped():
                return canvas
        except Exception:
            continue
    return canvases[0] if canvases else None


def _foco_em_campo_de_edicao(janela) -> bool:
    try:
        foco = janela.focus_get()
    except Exception:
        return False
    return _classe_widget(foco) in {
        "Entry",
        "TEntry",
        "Text",
        "Spinbox",
        "TCombobox",
        "Listbox",
    }


def _instalar_navegacao(janela, notebook, canvases) -> None:
    if getattr(janela, "_display_settings_navigation", False):
        return

    def ao_rolar(evento):
        # Ctrl+roda fica livre para futuros recursos de zoom/acessibilidade.
        if int(getattr(evento, "state", 0) or 0) & 0x0004:
            return None
        unidades = calcular_unidades_rolagem(evento)
        canvas = _canvas_ativo(janela, canvases, evento)
        return "break" if rolar_canvas(canvas, unidades) else None

    def rolar_pagina(direcao: int):
        if _foco_em_campo_de_edicao(janela):
            return None
        canvas = _canvas_ativo(janela, canvases)
        if canvas is None:
            return None
        try:
            canvas.yview_scroll(int(direcao), "pages")
            return "break"
        except Exception:
            return None

    def ir_extremo(posicao: float):
        if _foco_em_campo_de_edicao(janela):
            return None
        canvas = _canvas_ativo(janela, canvases)
        if canvas is None:
            return None
        try:
            canvas.yview_moveto(float(posicao))
            return "break"
        except Exception:
            return None

    def selecionar_aba(indice: int):
        if notebook is None:
            return None
        try:
            abas = notebook.tabs()
            if not abas:
                return None
            notebook.select(abas[indice % len(abas)])
            notebook.focus_set()
            return "break"
        except Exception:
            return None

    def alternar_aba(passo: int):
        if notebook is None:
            return None
        try:
            abas = list(notebook.tabs())
            atual = notebook.index(notebook.select())
        except Exception:
            return None
        return selecionar_aba(atual + passo) if abas else None

    janela.bind("<MouseWheel>", ao_rolar, add="+")
    janela.bind("<Button-4>", ao_rolar, add="+")
    janela.bind("<Button-5>", ao_rolar, add="+")
    janela.bind("<Prior>", lambda _e: rolar_pagina(-1), add="+")
    janela.bind("<Next>", lambda _e: rolar_pagina(1), add="+")
    janela.bind("<Home>", lambda _e: ir_extremo(0.0), add="+")
    janela.bind("<End>", lambda _e: ir_extremo(1.0), add="+")
    janela.bind("<Control-Key-1>", lambda _e: selecionar_aba(0), add="+")
    janela.bind("<Control-Key-2>", lambda _e: selecionar_aba(1), add="+")
    janela.bind("<Control-Tab>", lambda _e: alternar_aba(1), add="+")
    janela.bind(
        "<Control-Shift-Tab>",
        lambda _e: alternar_aba(-1),
        add="+",
    )

    janela._display_settings_navigation = True


def _estilizar_scrollbars(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Scrollbar):
            continue
        _configurar(
            widget,
            background=cores.DISPLAY_DARK_RAISED,
            activebackground=cores.DISPLAY_YELLOW_DARK,
            troughcolor=cores.DISPLAY_DARK,
            highlightbackground=cores.DISPLAY_DARK,
            highlightcolor=cores.DISPLAY_YELLOW_DARK,
            bd=0,
            relief=tk.FLAT,
            elementborderwidth=0,
            width=12,
            cursor="hand2",
        )


def _estilizar_header(janela, cores) -> None:
    titulo = None
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, tk.Label) and _texto_widget(widget) == "Configurações do sistema":
            titulo = widget
            break
    if titulo is None:
        return

    _configurar(titulo, foreground=cores.DISPLAY_WHITE)
    linha = getattr(titulo, "master", None)
    textos = getattr(linha, "master", None)
    cabecalho = getattr(textos, "master", None)
    if cabecalho is None:
        return

    _configurar(
        cabecalho,
        background=cores.DISPLAY_DARK_CARD,
        highlightbackground=cores.DISPLAY_BORDER,
        highlightcolor=cores.DISPLAY_YELLOW_DARK,
        highlightthickness=1,
    )

    for filho in getattr(cabecalho, "winfo_children", lambda: ())():
        if isinstance(filho, tk.Frame):
            try:
                largura = int(filho.cget("width") or 0)
            except Exception:
                largura = 0
            if 1 <= largura <= 8:
                _configurar(filho, background=cores.DISPLAY_YELLOW_DARK)

    for widget in _percorrer_widgets(cabecalho):
        texto = _texto_widget(widget)
        if texto == "ODIN":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_YELLOW,
                highlightbackground=cores.DISPLAY_BORDER,
                highlightthickness=1,
            )
        elif texto == "✕":
            _configurar(
                widget,
                background=cores.DISPLAY_DANGER_DARK,
                foreground=cores.DISPLAY_DANGER_LIGHT,
                activebackground=cores.DISPLAY_DANGER,
                activeforeground=cores.DISPLAY_WHITE,
            )


def _estilizar_notebook(janela, notebook, cores) -> None:
    try:
        estilo = ttk.Style(janela)
        estilo.configure(
            "Odin.TNotebook",
            background=cores.DISPLAY_DARK_CARD,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        estilo.configure(
            "Odin.TNotebook.Tab",
            background=cores.DISPLAY_DARK_RAISED,
            foreground=cores.DISPLAY_MUTED,
            padding=(24, 11),
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        estilo.map(
            "Odin.TNotebook.Tab",
            background=[
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
            foreground=[
                ("selected", cores.DISPLAY_INK),
                ("active", cores.DISPLAY_WHITE),
            ],
        )
    except Exception:
        pass

    if notebook is not None:
        try:
            notebook.configure(takefocus=True)
        except Exception:
            pass


def _accent_por_titulo(titulo: str, cores) -> str:
    mapa = {
        "Referências fixas": cores.DISPLAY_BLUE,
        "LEDs fixos": cores.DISPLAY_PURPLE,
        "Raio de seleção dos LEDs": cores.DISPLAY_YELLOW_DARK,
        "Armazenamento": cores.DISPLAY_SUCCESS,
        "Estado da câmera": cores.DISPLAY_BLUE,
        "Perfil de captura": cores.DISPLAY_BLUE,
        "Controles de imagem e posição": cores.DISPLAY_PURPLE,
        "Controles avançados da câmera": cores.DISPLAY_YELLOW_DARK,
        "Rotação da imagem": cores.DISPLAY_WARNING,
    }
    return mapa.get(titulo, cores.DISPLAY_YELLOW_DARK)


def _estilizar_cards(janela, cores) -> None:
    titulos = {
        "Referências fixas",
        "LEDs fixos",
        "Raio de seleção dos LEDs",
        "Armazenamento",
        "Estado da câmera",
        "Perfil de captura",
        "Controles de imagem e posição",
        "Controles avançados da câmera",
        "Rotação da imagem",
    }

    for label in _percorrer_widgets(janela):
        if not isinstance(label, tk.Label):
            continue
        titulo = _texto_widget(label)
        if titulo not in titulos:
            continue

        accent = _accent_por_titulo(titulo, cores)
        _configurar(label, foreground=accent)
        card = getattr(label, "master", None)
        if card is None:
            continue

        # Títulos criados pelo fluxo avançado ficam dentro do corpo do card.
        # Subimos até encontrar o frame que possui borda/highlight.
        atual = card
        for _ in range(4):
            try:
                espessura = int(atual.cget("highlightthickness") or 0)
            except Exception:
                espessura = 0
            if espessura > 0:
                card = atual
                break
            atual = getattr(atual, "master", None)
            if atual is None:
                break

        _configurar(
            card,
            background=cores.DISPLAY_DARK_RAISED,
            highlightbackground=cores.DISPLAY_BORDER,
            highlightcolor=accent,
            highlightthickness=1,
        )

        try:
            filhos = tuple(card.winfo_children())
        except Exception:
            filhos = ()
        for filho in filhos:
            if not isinstance(filho, tk.Frame):
                continue
            try:
                altura = int(filho.cget("height") or 0)
            except Exception:
                altura = 0
            if 2 <= altura <= 4:
                _configurar(filho, background=accent)
            elif altura == 1:
                _configurar(filho, background=cores.DISPLAY_BORDER)


def _estilo_especial_botao(texto: str, cores):
    estilos = {
        "Ref. aceso": (
            cores.DISPLAY_SUCCESS_DARK,
            cores.DISPLAY_SUCCESS_LIGHT,
            cores.DISPLAY_SUCCESS,
            cores.DISPLAY_INK,
        ),
        "Ref. apagado": (
            cores.DISPLAY_DANGER_DARK,
            cores.DISPLAY_DANGER_LIGHT,
            cores.DISPLAY_DANGER,
            cores.DISPLAY_WHITE,
        ),
        "Carregar refs.": (
            cores.DISPLAY_BLUE_DARK,
            cores.DISPLAY_BLUE_LIGHT,
            cores.DISPLAY_BLUE,
            cores.DISPLAY_WHITE,
        ),
        "Configurar LEDs": (
            cores.DISPLAY_PURPLE_DARK,
            cores.DISPLAY_PURPLE_LIGHT,
            cores.DISPLAY_PURPLE,
            cores.DISPLAY_WHITE,
        ),
        "Restaurar padrões da câmera": (
            cores.DISPLAY_DANGER_DARK,
            cores.DISPLAY_DANGER_LIGHT,
            cores.DISPLAY_DANGER,
            cores.DISPLAY_WHITE,
        ),
    }
    return estilos.get(texto)


def _estilizar_botoes_e_campos(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        classe = _classe_widget(widget)
        texto = _texto_widget(widget)

        if classe in {"Button", "Menubutton"}:
            especial = _estilo_especial_botao(texto, cores)
            if especial is not None:
                fundo, frente, hover, frente_hover = especial
                _configurar(
                    widget,
                    background=fundo,
                    foreground=frente,
                    activebackground=hover,
                    activeforeground=frente_hover,
                    highlightbackground=hover,
                    highlightcolor=hover,
                    highlightthickness=1,
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                )

        elif classe in {"Spinbox", "Entry", "Text"}:
            _configurar(
                widget,
                background=cores.DISPLAY_DARK,
                foreground=cores.DISPLAY_WHITE,
                insertbackground=cores.DISPLAY_YELLOW,
                selectbackground=cores.DISPLAY_BLUE,
                selectforeground=cores.DISPLAY_WHITE,
                highlightbackground=cores.DISPLAY_BORDER,
                highlightcolor=cores.DISPLAY_YELLOW_DARK,
                highlightthickness=1,
                relief=tk.FLAT,
            )
        elif classe == "Scale":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                activebackground=cores.DISPLAY_YELLOW_DARK,
                troughcolor=cores.DISPLAY_DARK,
                highlightthickness=0,
                bd=0,
            )
        elif classe in {"Checkbutton", "Radiobutton"}:
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_WHITE,
                activebackground=cores.DISPLAY_DARK_RAISED,
                activeforeground=cores.DISPLAY_YELLOW,
                selectcolor=cores.DISPLAY_DARK,
                highlightbackground=cores.DISPLAY_BORDER,
            )


def _atualizar_ajuda_rodape(janela, cores) -> None:
    prefixo = "As alterações serão salvas no arquivo de configuração de ODIN."
    ajuda = (
        "  •  Roda do mouse/PgUp/PgDn: navegar  •  Ctrl+1/Ctrl+2: abas  "
        "•  Ctrl+Enter: salvar  •  Esc: fechar"
    )
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Label):
            continue
        texto = _texto_widget(widget)
        if not texto.startswith(prefixo):
            continue
        _configurar(
            widget,
            text=prefixo + ajuda,
            foreground=cores.DISPLAY_MUTED,
            wraplength=520,
            justify=tk.LEFT,
        )
        break


def aplicar_ux_configuracoes_display(view, janela) -> None:
    """Refina a janela de configurações e habilita navegação completa."""
    if janela is None:
        return

    # Importação tardia evita ciclo durante a carga da classe ODINView.
    from src.platform import display_theme as cores

    try:
        cores.aplicar_tema_arvore(janela)
    except Exception:
        pass

    _configurar(janela, background=cores.DISPLAY_DARK)
    try:
        janela.minsize(760, 640)
    except Exception:
        pass

    notebook = _obter_notebook(janela)
    canvases = _obter_canvases_rolagem(janela)

    _estilizar_header(janela, cores)
    _estilizar_notebook(janela, notebook, cores)
    _estilizar_cards(janela, cores)
    _estilizar_botoes_e_campos(janela, cores)
    _estilizar_scrollbars(janela, cores)
    _atualizar_ajuda_rodape(janela, cores)
    _instalar_navegacao(janela, notebook, canvases)

    for canvas in canvases:
        _configurar(
            canvas,
            background=cores.DISPLAY_DARK_CARD,
            highlightbackground=cores.DISPLAY_BORDER,
            highlightthickness=0,
        )
        try:
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    try:
        janela.update_idletasks()
    except Exception:
        pass


def instalar_ux_configuracoes_display() -> None:
    """Envolve a abertura original sem alterar a branch raspberry-pi-3."""
    from src.ui.main_window import ODINView

    original = ODINView.abrir_janela_configuracoes
    if getattr(original, _PATCH_MARKER, False):
        return

    def abrir_com_ux(self, *args, **kwargs):
        try:
            janelas_antes = tuple(self.root.winfo_children())
        except Exception:
            janelas_antes = ()

        retorno = original(self, *args, **kwargs)
        janela = _encontrar_janela_configuracoes(
            self.root,
            janelas_antes=janelas_antes,
        )
        aplicar_ux_configuracoes_display(self, janela)
        return retorno

    setattr(abrir_com_ux, _PATCH_MARKER, True)
    setattr(abrir_com_ux, "_odin_original", original)
    ODINView.abrir_janela_configuracoes = abrir_com_ux
