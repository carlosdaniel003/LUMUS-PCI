from __future__ import annotations

import tkinter as tk
from tkinter import ttk


_PATCH_OPEN = "_odin_display_settings_redesign_open"
_PATCH_THEME = "_odin_display_settings_redesign_theme"


SECTION_ACCENTS = {
    "Referências fixas": "info",
    "LEDs fixos": "selection",
    "Raio de seleção dos LEDs": "primary",
    "Armazenamento": "success",
    "Estado da câmera": "info",
    "Perfil de captura": "info",
    "Controles de imagem e posição": "selection",
    "Controles avançados da câmera": "primary",
    "Rotação da imagem": "warning",
}


BUTTON_ROLES = {
    "Ref. aceso": "success_outline",
    "Ref. apagado": "danger_outline",
    "Carregar refs.": "info_outline",
    "Configurar LEDs": "selection_outline",
    "Salvar LEDs": "primary",
    "Restaurar padrões da câmera": "danger_outline",
    "Salvar": "primary",
    "Cancelar": "neutral",
}


def calcular_tamanho_janela(
    largura_tela: int,
    altura_tela: int,
) -> tuple[int, int]:
    """Calcula um tamanho confortável sem ultrapassar o monitor."""
    largura = min(1040, max(820, int(largura_tela) - 120))
    altura = min(820, max(680, int(altura_tela) - 140))
    return largura, altura


def texto_ajuda_rodape() -> str:
    return (
        "As alterações só são aplicadas ao salvar.  •  "
        "Roda do mouse: navegar  •  Ctrl+1/2: abas  •  "
        "Ctrl+Enter: salvar  •  Esc: fechar"
    )


def _percorrer_widgets(widget):
    yield widget
    try:
        filhos = tuple(widget.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        yield from _percorrer_widgets(filho)


def _texto(widget) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _classe(widget) -> str:
    try:
        return str(widget.winfo_class())
    except Exception:
        return type(widget).__name__


def _configurar(widget, **opcoes) -> None:
    try:
        widget.configure(**opcoes)
    except Exception:
        pass


def _encontrar_janela_configuracoes(root, anteriores=()):
    anteriores = set(anteriores or ())
    candidatas = []
    try:
        filhos = tuple(root.winfo_children())
    except Exception:
        filhos = ()

    for widget in filhos:
        if not isinstance(widget, tk.Toplevel):
            continue
        try:
            if widget.winfo_exists() and widget.title() == "Configurações - ODIN":
                candidatas.append(widget)
        except Exception:
            continue

    novas = [janela for janela in candidatas if janela not in anteriores]
    if novas:
        return novas[-1]
    return candidatas[-1] if candidatas else None


def _encontrar_notebook(janela):
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, ttk.Notebook):
            return widget
    return None


def _encontrar_card(label):
    atual = getattr(label, "master", None)
    candidato = atual
    for _ in range(6):
        if atual is None:
            break
        try:
            espessura = int(atual.cget("highlightthickness") or 0)
        except Exception:
            espessura = 0
        if espessura > 0:
            return atual
        candidato = atual
        atual = getattr(atual, "master", None)
    return candidato


def _cor_accent(nome: str, cores) -> str:
    papel = SECTION_ACCENTS.get(nome, "primary")
    return {
        "info": cores.DISPLAY_BLUE,
        "selection": cores.DISPLAY_PURPLE,
        "primary": cores.DISPLAY_YELLOW_DARK,
        "success": cores.DISPLAY_SUCCESS,
        "warning": cores.DISPLAY_WARNING,
    }[papel]


def _ajustar_geometria(janela) -> None:
    if getattr(janela, "_display_redesign_geometry", False):
        return
    try:
        janela.update_idletasks()
        largura_tela = janela.winfo_screenwidth()
        altura_tela = janela.winfo_screenheight()
        largura, altura = calcular_tamanho_janela(largura_tela, altura_tela)
        x = max(20, int((largura_tela - largura) / 2))
        y = max(20, int((altura_tela - altura) / 2))
        janela.geometry(f"{largura}x{altura}+{x}+{y}")
        janela.minsize(820, 680)
        janela._display_redesign_geometry = True
    except Exception:
        pass


def _estilizar_cabecalho(janela, cores) -> None:
    titulo = None
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, tk.Label) and _texto(widget) == "Configurações do sistema":
            titulo = widget
            break
    if titulo is None:
        return

    linha = getattr(titulo, "master", None)
    bloco_textos = getattr(linha, "master", None)
    cabecalho = getattr(bloco_textos, "master", None)
    if cabecalho is None:
        return

    _configurar(
        cabecalho,
        background=cores.DISPLAY_DARK_CARD,
        highlightbackground=cores.DISPLAY_BORDER,
        highlightcolor=cores.DISPLAY_BORDER,
        highlightthickness=1,
    )
    try:
        cabecalho.pack_configure(pady=(0, 12))
    except Exception:
        pass

    _configurar(
        titulo,
        font=("Segoe UI", 18, "bold"),
        foreground=cores.DISPLAY_WHITE,
        background=cores.DISPLAY_DARK_CARD,
    )

    if bloco_textos is not None:
        _configurar(bloco_textos, background=cores.DISPLAY_DARK_CARD)
        try:
            bloco_textos.pack_configure(padx=18, pady=14)
        except Exception:
            pass

    for widget in _percorrer_widgets(cabecalho):
        texto = _texto(widget)
        if isinstance(widget, tk.Label) and texto.startswith("Ajuste referências"):
            _configurar(
                widget,
                font=("Segoe UI", 9),
                foreground=cores.DISPLAY_MUTED,
                background=cores.DISPLAY_DARK_CARD,
            )
        elif texto == "ODIN":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_YELLOW,
                highlightbackground=cores.DISPLAY_BORDER,
                highlightthickness=1,
                padx=12,
                pady=5,
            )
        elif texto == "✕":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_CARD,
                foreground=cores.DISPLAY_MUTED,
                activebackground=cores.DISPLAY_DANGER,
                activeforeground=cores.DISPLAY_WHITE,
                highlightthickness=0,
            )

    try:
        filhos = tuple(cabecalho.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        if not isinstance(filho, tk.Frame):
            continue
        try:
            largura = int(filho.cget("width") or 0)
        except Exception:
            largura = 0
        if 1 <= largura <= 8:
            _configurar(filho, background=cores.DISPLAY_YELLOW_DARK, width=4)


def _estilizar_notebook(janela, notebook, cores) -> None:
    if notebook is None:
        return
    try:
        estilo = ttk.Style(janela)
        estilo.configure(
            "Odin.TNotebook",
            background=cores.DISPLAY_DARK,
            borderwidth=0,
            tabmargins=(0, 0, 0, 6),
        )
        estilo.configure(
            "Odin.TNotebook.Tab",
            background=cores.DISPLAY_DARK_RAISED,
            foreground=cores.DISPLAY_MUTED,
            padding=(20, 10),
            font=("Segoe UI", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        estilo.map(
            "Odin.TNotebook.Tab",
            background=[
                ("selected", cores.DISPLAY_DARK_CARD),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
            foreground=[
                ("selected", cores.DISPLAY_YELLOW),
                ("active", cores.DISPLAY_WHITE),
            ],
            bordercolor=[
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_BORDER_STRONG),
            ],
            lightcolor=[("selected", cores.DISPLAY_YELLOW_DARK)],
            darkcolor=[("selected", cores.DISPLAY_YELLOW_DARK)],
        )
        notebook.configure(style="Odin.TNotebook", takefocus=True)
    except Exception:
        pass


def _remover_faixas_excessivas(card, cores) -> None:
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
            try:
                filho.pack_forget()
            except Exception:
                _configurar(filho, height=1, background=cores.DISPLAY_BORDER)
        elif altura == 1:
            _configurar(filho, background=cores.DISPLAY_BORDER)


def _adicionar_barra_lateral(card, accent) -> None:
    barra = getattr(card, "_display_redesign_accent", None)
    if barra is not None:
        _configurar(barra, background=accent)
        return
    try:
        barra = tk.Frame(card, bg=accent, width=4, bd=0)
        barra.place(x=0, y=0, relheight=1.0)
        card._display_redesign_accent = barra
    except Exception:
        pass


def _estilizar_cards(janela, cores) -> None:
    for label in _percorrer_widgets(janela):
        if not isinstance(label, tk.Label):
            continue
        titulo = _texto(label)
        if titulo not in SECTION_ACCENTS:
            continue

        card = _encontrar_card(label)
        if card is None:
            continue
        accent = _cor_accent(titulo, cores)

        _configurar(
            card,
            background=cores.DISPLAY_DARK_RAISED,
            highlightbackground=cores.DISPLAY_BORDER,
            highlightcolor=accent,
            highlightthickness=1,
        )
        try:
            card.pack_configure(padx=(2, 10), pady=(0, 12))
        except Exception:
            pass

        _remover_faixas_excessivas(card, cores)
        _adicionar_barra_lateral(card, accent)

        _configurar(
            label,
            text=titulo,
            font=("Segoe UI", 11, "bold"),
            foreground=cores.DISPLAY_WHITE,
            background=cores.DISPLAY_DARK_RAISED,
        )
        try:
            label.pack_configure(padx=18, pady=(14, 6))
        except Exception:
            pass

        for widget in _percorrer_widgets(card):
            if widget is card:
                continue
            classe = _classe(widget)
            if classe in {"Frame", "Label", "Checkbutton", "Radiobutton", "Scale"}:
                atual = None
                try:
                    atual = str(widget.cget("background"))
                except Exception:
                    pass
                if atual is not None:
                    _configurar(widget, background=cores.DISPLAY_DARK_RAISED)
            if isinstance(widget, tk.Label) and widget is not label:
                texto = _texto(widget)
                if texto and texto not in SECTION_ACCENTS:
                    try:
                        fonte = str(widget.cget("font"))
                    except Exception:
                        fonte = ""
                    if "bold" not in fonte.lower():
                        _configurar(widget, foreground=cores.DISPLAY_MUTED)


def _estilo_botao(papel: str, cores):
    return {
        "primary": (
            cores.DISPLAY_YELLOW_DARK,
            cores.DISPLAY_INK,
            cores.DISPLAY_YELLOW,
            cores.DISPLAY_INK,
            cores.DISPLAY_YELLOW_DARK,
        ),
        "success_outline": (
            cores.DISPLAY_DARK_CARD,
            cores.DISPLAY_SUCCESS_LIGHT,
            cores.DISPLAY_SUCCESS_DARK,
            cores.DISPLAY_SUCCESS_LIGHT,
            cores.DISPLAY_SUCCESS,
        ),
        "danger_outline": (
            cores.DISPLAY_DARK_CARD,
            cores.DISPLAY_DANGER_LIGHT,
            cores.DISPLAY_DANGER_DARK,
            cores.DISPLAY_DANGER_LIGHT,
            cores.DISPLAY_DANGER,
        ),
        "info_outline": (
            cores.DISPLAY_DARK_CARD,
            cores.DISPLAY_BLUE_LIGHT,
            cores.DISPLAY_BLUE_DARK,
            cores.DISPLAY_BLUE_LIGHT,
            cores.DISPLAY_BLUE,
        ),
        "selection_outline": (
            cores.DISPLAY_DARK_CARD,
            cores.DISPLAY_PURPLE_LIGHT,
            cores.DISPLAY_PURPLE_DARK,
            cores.DISPLAY_PURPLE_LIGHT,
            cores.DISPLAY_PURPLE,
        ),
        "neutral": (
            cores.DISPLAY_DARK_RAISED,
            cores.DISPLAY_WHITE,
            cores.DISPLAY_DARK_HOVER,
            cores.DISPLAY_WHITE,
            cores.DISPLAY_BORDER_STRONG,
        ),
    }[papel]


def _estilizar_botoes(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        if _classe(widget) not in {"Button", "Menubutton"}:
            continue
        texto = _texto(widget)
        papel = BUTTON_ROLES.get(texto)
        if papel is None:
            continue
        fundo, frente, hover, frente_hover, borda = _estilo_botao(papel, cores)
        _configurar(
            widget,
            background=fundo,
            foreground=frente,
            activebackground=hover,
            activeforeground=frente_hover,
            highlightbackground=borda,
            highlightcolor=borda,
            highlightthickness=1,
            relief=tk.FLAT,
            bd=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            takefocus=True,
            padx=14,
            pady=7,
        )


def _estilizar_campos(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        classe = _classe(widget)
        if classe in {"Spinbox", "Entry", "Text"}:
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
                bd=0,
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


def _estilizar_rolagem(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, tk.Scrollbar):
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
                width=11,
                cursor="hand2",
            )
        elif isinstance(widget, tk.Canvas):
            try:
                comando = str(widget.cget("yscrollcommand") or "")
            except Exception:
                comando = ""
            if comando:
                _configurar(
                    widget,
                    background=cores.DISPLAY_DARK_CARD,
                    highlightthickness=0,
                    bd=0,
                )


def _estilizar_rodape(janela, cores) -> None:
    for label in _percorrer_widgets(janela):
        if not isinstance(label, tk.Label):
            continue
        texto = _texto(label)
        if not texto.startswith("As alterações"):
            continue
        frame = getattr(label, "master", None)
        _configurar(
            label,
            text=texto_ajuda_rodape(),
            font=("Segoe UI", 8),
            foreground=cores.DISPLAY_MUTED,
            background=cores.DISPLAY_DARK_ALT,
            wraplength=650,
            justify=tk.LEFT,
        )
        if frame is not None:
            _configurar(frame, background=cores.DISPLAY_DARK_ALT)
            try:
                frame.pack_configure(fill=tk.X, pady=(12, 0), ipady=8)
            except Exception:
                pass
            for widget in _percorrer_widgets(frame):
                if isinstance(widget, tk.Frame):
                    _configurar(widget, background=cores.DISPLAY_DARK_ALT)
        break


def aplicar_redesign_configuracoes(view, janela) -> None:
    """Aplica uma composição mais limpa e hierárquica à janela."""
    if janela is None:
        return

    from src.platform import display_theme as cores

    _ajustar_geometria(janela)
    _configurar(janela, background=cores.DISPLAY_DARK)
    notebook = _encontrar_notebook(janela)

    _estilizar_cabecalho(janela, cores)
    _estilizar_notebook(janela, notebook, cores)
    _estilizar_cards(janela, cores)
    _estilizar_botoes(janela, cores)
    _estilizar_campos(janela, cores)
    _estilizar_rolagem(janela, cores)
    _estilizar_rodape(janela, cores)

    try:
        janela.update_idletasks()
    except Exception:
        pass


def _janelas_configuracoes(root):
    try:
        filhos = tuple(root.winfo_children())
    except Exception:
        filhos = ()
    for widget in filhos:
        if not isinstance(widget, tk.Toplevel):
            continue
        try:
            if widget.winfo_exists() and widget.title() == "Configurações - ODIN":
                yield widget
        except Exception:
            continue


def instalar_redesign_configuracoes_display() -> None:
    """Instala o redesenho somente no perfil da branch display."""
    from src.platform.display_theme import DisplayThemeMixin
    from src.ui.main_window import ODINView

    original_abrir = ODINView.abrir_janela_configuracoes
    if not getattr(original_abrir, _PATCH_OPEN, False):
        def abrir_com_redesign(self, *args, **kwargs):
            try:
                anteriores = tuple(self.root.winfo_children())
            except Exception:
                anteriores = ()
            retorno = original_abrir(self, *args, **kwargs)
            janela = _encontrar_janela_configuracoes(self.root, anteriores)
            aplicar_redesign_configuracoes(self, janela)
            if janela is not None:
                for atraso in (0, 80, 220):
                    try:
                        janela.after(
                            atraso,
                            lambda j=janela, v=self: aplicar_redesign_configuracoes(v, j),
                        )
                    except Exception:
                        break
            return retorno

        setattr(abrir_com_redesign, _PATCH_OPEN, True)
        setattr(abrir_com_redesign, "_odin_original", original_abrir)
        ODINView.abrir_janela_configuracoes = abrir_com_redesign

    original_tema = DisplayThemeMixin._aplicar_tema_display_agora
    if not getattr(original_tema, _PATCH_THEME, False):
        def aplicar_tema_e_redesign(self):
            retorno = original_tema(self)
            root = getattr(self, "root", None)
            if root is None:
                return retorno
            view = getattr(self, "view", None)
            for janela in _janelas_configuracoes(root):
                aplicar_redesign_configuracoes(view, janela)
            return retorno

        setattr(aplicar_tema_e_redesign, _PATCH_THEME, True)
        setattr(aplicar_tema_e_redesign, "_odin_original", original_tema)
        DisplayThemeMixin._aplicar_tema_display_agora = aplicar_tema_e_redesign
