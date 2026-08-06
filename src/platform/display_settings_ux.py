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


def _classe_widget(widget) -> str:
    try:
        return str(widget.winfo_class())
    except Exception:
        return type(widget).__name__


def calcular_unidades_rolagem(evento, unidades: int = _SCROLL_UNITS) -> int:
    """Converte a roda do Windows/macOS e os botões 4/5 do Linux."""
    numero = getattr(evento, "num", None)
    if numero == 4:
        return -abs(int(unidades))
    if numero == 5:
        return abs(int(unidades))

    delta = int(getattr(evento, "delta", 0) or 0)
    if delta == 0:
        return 0

    passos = max(1, abs(delta) // 120)
    direcao = -1 if delta > 0 else 1
    return direcao * passos * abs(int(unidades))


def rolar_canvas(canvas, unidades: int) -> bool:
    """Rola o Canvas sem ultrapassar os limites do conteúdo."""
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
            if widget.winfo_exists() and widget.title() == "Configurações - ODIN":
                candidatas.append(widget)
        except Exception:
            continue

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


def aplicar_ux_configuracoes_display(view, janela) -> None:
    """Instala somente navegação e rolagem; não altera a geometria visual."""
    if janela is None or getattr(janela, "_display_settings_navigation", False):
        return

    notebook = _obter_notebook(janela)
    canvases = _obter_canvases_rolagem(janela)

    def ao_rolar(evento):
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
            abas = list(notebook.tabs())
            if not abas:
                return None
            notebook.select(abas[indice % len(abas)])
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


def instalar_ux_configuracoes_display() -> None:
    """Compatibilidade: envolve a abertura original uma única vez."""
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
