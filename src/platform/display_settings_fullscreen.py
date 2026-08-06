from __future__ import annotations

import tkinter as tk
from tkinter import ttk


_PATCH_OPEN = "_odin_display_settings_fullscreen_open"
_PATCH_THEME = "_odin_display_settings_fullscreen_theme"


def calcular_margem_responsiva(largura: int) -> int:
    """Centraliza o conteúdo sem desperdiçar espaço em telas menores."""
    largura = max(0, int(largura))
    if largura < 1100:
        return 18
    if largura < 1500:
        return 42
    return min(220, max(70, int((largura - 1320) / 2)))


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


def _encontrar_janela(root, anteriores=()):
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


def _janelas_configuracoes(root):
    janela = _encontrar_janela(root)
    if janela is not None:
        yield janela


def _notebook(janela):
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, ttk.Notebook):
            return widget
    return None


def _canvases_rolagem(janela):
    resultado = []
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Canvas):
            continue
        try:
            comando = str(widget.cget("yscrollcommand") or "")
        except Exception:
            comando = ""
        if comando:
            resultado.append(widget)
    return resultado


def _labels_secao(janela):
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
    for widget in _percorrer_widgets(janela):
        if isinstance(widget, tk.Label) and _texto(widget) in titulos:
            yield widget


def _card_da_label(label):
    atual = getattr(label, "master", None)
    candidato = atual
    for _ in range(7):
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


def _ativar_tela_cheia(janela) -> None:
    if getattr(janela, "_display_settings_fullscreen_active", False):
        return
    try:
        janela.withdraw()
    except Exception:
        pass
    try:
        janela.attributes("-fullscreen", True)
    except Exception:
        try:
            janela.state("zoomed")
        except Exception:
            try:
                largura = janela.winfo_screenwidth()
                altura = janela.winfo_screenheight()
                janela.geometry(f"{largura}x{altura}+0+0")
            except Exception:
                pass
    try:
        janela.overrideredirect(False)
    except Exception:
        pass
    try:
        janela.deiconify()
        janela.lift()
        janela.focus_force()
    except Exception:
        pass
    janela._display_settings_fullscreen_active = True


def _estilizar_notebook(janela, notebook, cores) -> None:
    if notebook is None:
        return
    try:
        estilo = ttk.Style(janela)
        estilo.theme_use("clam")
        estilo.layout(
            "Odin.TNotebook",
            [("Notebook.client", {"sticky": "nswe"})],
        )
        estilo.configure(
            "Odin.TNotebook",
            background=cores.DISPLAY_DARK,
            borderwidth=0,
            relief="flat",
            tabmargins=(0, 0, 0, 8),
            lightcolor=cores.DISPLAY_DARK,
            darkcolor=cores.DISPLAY_DARK,
            bordercolor=cores.DISPLAY_DARK,
        )
        estilo.configure(
            "Odin.TNotebook.Tab",
            background=cores.DISPLAY_DARK_RAISED,
            foreground=cores.DISPLAY_MUTED,
            padding=(22, 11),
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            lightcolor=cores.DISPLAY_DARK_RAISED,
            darkcolor=cores.DISPLAY_DARK_RAISED,
            bordercolor=cores.DISPLAY_DARK_RAISED,
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
            lightcolor=[("selected", cores.DISPLAY_DARK_CARD)],
            darkcolor=[("selected", cores.DISPLAY_DARK_CARD)],
            bordercolor=[("selected", cores.DISPLAY_DARK_CARD)],
        )
        notebook.configure(style="Odin.TNotebook", takefocus=True)
    except Exception:
        pass


def _limpar_bordas_brancas(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        classe = _classe(widget)
        if classe in {"Frame", "Canvas", "LabelFrame", "TFrame"}:
            _configurar(widget, bd=0, relief=tk.FLAT)
            try:
                espessura = int(widget.cget("highlightthickness") or 0)
            except Exception:
                espessura = 0
            if espessura > 0:
                _configurar(
                    widget,
                    highlightbackground=cores.DISPLAY_BORDER,
                    highlightcolor=cores.DISPLAY_BORDER,
                )
        elif classe in {"Entry", "Spinbox", "Text", "Listbox"}:
            _configurar(
                widget,
                bd=0,
                relief=tk.FLAT,
                highlightbackground=cores.DISPLAY_BORDER,
                highlightcolor=cores.DISPLAY_YELLOW_DARK,
                highlightthickness=1,
            )


def _organizar_linha_controle(row, cores) -> None:
    if getattr(row, "_display_settings_row_aligned", False):
        return
    filhos = []
    try:
        filhos = list(row.winfo_children())
    except Exception:
        return

    topo = None
    ajuste = None
    descricao = None
    automatico = None
    for filho in filhos:
        if isinstance(filho, tk.Frame):
            descendentes = list(_percorrer_widgets(filho))
            if any(_classe(item) == "Scale" for item in descendentes):
                ajuste = filho
            elif any(_classe(item) in {"Checkbutton", "Radiobutton"} for item in descendentes):
                topo = filho
        elif _classe(filho) in {"Checkbutton", "Radiobutton"}:
            automatico = filho
        elif isinstance(filho, tk.Label):
            descricao = filho

    if topo is None or ajuste is None:
        return

    _configurar(row, background=cores.DISPLAY_DARK_RAISED)
    try:
        row.pack_configure(fill=tk.X, expand=True, padx=18, pady=(8, 14))
    except Exception:
        pass

    try:
        topo.pack_forget()
        ajuste.pack_forget()
        if automatico is not None:
            automatico.pack_forget()
        if descricao is not None:
            descricao.pack_forget()
    except Exception:
        return

    topo.grid(row=0, column=0, sticky="ew")
    row.grid_columnconfigure(0, weight=1)
    linha = 1
    if automatico is not None:
        automatico.grid(row=linha, column=0, sticky="w", pady=(5, 2))
        linha += 1
    ajuste.grid(row=linha, column=0, sticky="ew", pady=(7, 3))
    linha += 1
    if descricao is not None:
        descricao.grid(row=linha, column=0, sticky="ew", pady=(2, 0))

    _configurar(topo, background=cores.DISPLAY_DARK_RAISED)
    _configurar(ajuste, background=cores.DISPLAY_DARK_RAISED)

    try:
        elementos_topo = list(topo.winfo_children())
    except Exception:
        elementos_topo = []
    if elementos_topo:
        for item in elementos_topo:
            try:
                item.pack_forget()
            except Exception:
                pass
        topo.grid_columnconfigure(0, weight=1)
        topo.grid_columnconfigure(1, weight=0)
        elementos_topo[0].grid(row=0, column=0, sticky="w")
        for indice, item in enumerate(elementos_topo[1:], start=1):
            item.grid(row=0, column=indice, sticky="e", padx=(16, 0))

    try:
        elementos_ajuste = list(ajuste.winfo_children())
    except Exception:
        elementos_ajuste = []
    if elementos_ajuste:
        for item in elementos_ajuste:
            try:
                item.pack_forget()
            except Exception:
                pass
        ajuste.grid_columnconfigure(0, weight=1)
        escala = next((item for item in elementos_ajuste if _classe(item) == "Scale"), None)
        valor = next((item for item in elementos_ajuste if item is not escala), None)
        if escala is not None:
            escala.grid(row=0, column=0, sticky="ew")
        if valor is not None:
            valor.grid(row=0, column=1, sticky="e", padx=(14, 0))
            _configurar(valor, width=7, anchor="e")

    row._display_settings_row_aligned = True


def _alinhar_controles(janela, cores) -> None:
    processados = set()
    for widget in _percorrer_widgets(janela):
        if _classe(widget) != "Scale":
            continue
        ajuste = getattr(widget, "master", None)
        row = getattr(ajuste, "master", None)
        if row is None or row in processados:
            continue
        processados.add(row)
        _organizar_linha_controle(row, cores)


def _aplicar_margens_responsivas(janela, cores) -> None:
    if getattr(janela, "_display_settings_responsive_bound", False):
        return

    cards = []
    for label in _labels_secao(janela):
        card = _card_da_label(label)
        if card is not None and card not in cards:
            cards.append(card)

    def atualizar(evento=None):
        largura = getattr(evento, "width", None)
        if largura is None:
            try:
                largura = janela.winfo_width()
            except Exception:
                largura = 1200
        margem = calcular_margem_responsiva(largura)
        for card in cards:
            try:
                card.pack_configure(padx=(margem, margem), pady=(0, 14))
            except Exception:
                pass
        for canvas in _canvases_rolagem(janela):
            _configurar(canvas, background=cores.DISPLAY_DARK)

    janela.bind("<Configure>", atualizar, add="+")
    janela._display_settings_responsive_bound = True
    try:
        janela.after_idle(atualizar)
    except Exception:
        atualizar()


def _estilizar_acoes(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        if _classe(widget) not in {"Button", "Menubutton"}:
            continue
        texto = _texto(widget)
        if texto in {"Salvar", "Salvar LEDs"}:
            _configurar(
                widget,
                background=cores.DISPLAY_YELLOW_DARK,
                foreground=cores.DISPLAY_INK,
                activebackground=cores.DISPLAY_YELLOW,
                activeforeground=cores.DISPLAY_INK,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
                padx=18,
                pady=9,
                font=("Segoe UI", 10, "bold"),
            )
        elif texto in {"Cancelar", "Fechar"}:
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_WHITE,
                activebackground=cores.DISPLAY_DARK_HOVER,
                activeforeground=cores.DISPLAY_WHITE,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
                padx=18,
                pady=9,
                font=("Segoe UI", 10, "bold"),
            )
        elif texto == "✕":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_CARD,
                foreground=cores.DISPLAY_MUTED,
                activebackground=cores.DISPLAY_DANGER,
                activeforeground=cores.DISPLAY_WHITE,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
            )
        else:
            _configurar(
                widget,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
                padx=14,
                pady=7,
            )


def aplicar_configuracoes_fullscreen(view, janela) -> None:
    if janela is None:
        return
    from src.platform import display_theme as cores

    _ativar_tela_cheia(janela)
    _configurar(janela, background=cores.DISPLAY_DARK)
    _estilizar_notebook(janela, _notebook(janela), cores)
    _limpar_bordas_brancas(janela, cores)
    _alinhar_controles(janela, cores)
    _aplicar_margens_responsivas(janela, cores)
    _estilizar_acoes(janela, cores)

    for canvas in _canvases_rolagem(janela):
        _configurar(
            canvas,
            background=cores.DISPLAY_DARK,
            highlightthickness=0,
            bd=0,
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


def instalar_configuracoes_fullscreen_display() -> None:
    from src.platform.display_theme import DisplayThemeMixin
    from src.ui.main_window import ODINView

    original_abrir = ODINView.abrir_janela_configuracoes
    if not getattr(original_abrir, _PATCH_OPEN, False):
        def abrir_fullscreen(self, *args, **kwargs):
            try:
                anteriores = tuple(self.root.winfo_children())
            except Exception:
                anteriores = ()
            retorno = original_abrir(self, *args, **kwargs)
            janela = _encontrar_janela(self.root, anteriores)
            aplicar_configuracoes_fullscreen(self, janela)
            if janela is not None:
                for atraso in (0, 80, 250, 600):
                    try:
                        janela.after(
                            atraso,
                            lambda j=janela, v=self: aplicar_configuracoes_fullscreen(v, j),
                        )
                    except Exception:
                        break
            return retorno

        setattr(abrir_fullscreen, _PATCH_OPEN, True)
        setattr(abrir_fullscreen, "_odin_original", original_abrir)
        ODINView.abrir_janela_configuracoes = abrir_fullscreen

    original_tema = DisplayThemeMixin._aplicar_tema_display_agora
    if not getattr(original_tema, _PATCH_THEME, False):
        def tema_e_fullscreen(self):
            retorno = original_tema(self)
            root = getattr(self, "root", None)
            if root is None:
                return retorno
            view = getattr(self, "view", None)
            for janela in _janelas_configuracoes(root):
                aplicar_configuracoes_fullscreen(view, janela)
            return retorno

        setattr(tema_e_fullscreen, _PATCH_THEME, True)
        setattr(tema_e_fullscreen, "_odin_original", original_tema)
        DisplayThemeMixin._aplicar_tema_display_agora = tema_e_fullscreen
