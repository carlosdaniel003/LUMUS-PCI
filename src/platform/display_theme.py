from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.main_window import ODINView
from src.ui.operation_window_raspberry import RaspberryOperationWindow


# Paleta solicitada para a branch display.
DISPLAY_YELLOW = "#F5C518"  # rgb(245, 197, 24) | hsl(47, 92%, 53%)
DISPLAY_BLUE = "#2596BE"  # rgb(37, 150, 190) | hsl(196, 67%, 45%)

# Variações derivadas apenas para manter profundidade e contraste visual.
DISPLAY_BLUE_DARK = "#1C7898"
DISPLAY_BLUE_DEEP = "#104A60"
DISPLAY_BLUE_LIGHT = "#D9F3FC"
DISPLAY_YELLOW_DARK = "#D7A900"
DISPLAY_INK = "#102A35"
DISPLAY_WHITE = "#FFFFFF"


_DARK_BACKGROUND_MAP = {
    "#030712": DISPLAY_BLUE_DEEP,
    "#050b14": DISPLAY_BLUE_DEEP,
    "#020617": DISPLAY_BLUE_DEEP,
    "#07111f": DISPLAY_BLUE_DARK,
    "#0b1220": DISPLAY_BLUE_DARK,
    "#0b1626": DISPLAY_BLUE,
    "#0f172a": DISPLAY_BLUE_DARK,
    "#122033": DISPLAY_BLUE_DARK,
    "#1e293b": DISPLAY_BLUE_DARK,
    "#334155": DISPLAY_BLUE,
    "#374151": DISPLAY_BLUE_DARK,
    "#475569": DISPLAY_BLUE_DARK,
    "#1e3a5f": DISPLAY_BLUE,
    "#1e3a8a": DISPLAY_BLUE,
    "#1d4ed8": DISPLAY_BLUE,
}

_ACCENT_MAP = {
    "#38bdf8": DISPLAY_YELLOW,
    "#22d3ee": DISPLAY_YELLOW,
    "#fbbf24": DISPLAY_YELLOW,
    "#f59e0b": DISPLAY_YELLOW,
    "#2563eb": DISPLAY_YELLOW,
}

_MUTED_FOREGROUND_MAP = {
    "#cbd5e1": DISPLAY_WHITE,
    "#94a3b8": DISPLAY_BLUE_LIGHT,
    "#e2e8f0": DISPLAY_WHITE,
    "#f9fafb": DISPLAY_WHITE,
    "#bfdbfe": DISPLAY_BLUE_LIGHT,
}

_BORDER_OPTIONS = {
    "highlightbackground",
    "highlightcolor",
    "bordercolor",
    "lightcolor",
    "darkcolor",
}

_FOREGROUND_OPTIONS = {
    "foreground",
    "fg",
    "activeforeground",
    "disabledforeground",
    "insertbackground",
    "selectforeground",
}

_BACKGROUND_OPTIONS = {
    "background",
    "bg",
    "activebackground",
    "fieldbackground",
    "selectbackground",
    "troughcolor",
    "selectcolor",
}


def _normalizar_cor(valor) -> str:
    return str(valor or "").strip().lower()


def mapear_cor_display(opcao: str, valor):
    """Converte a paleta anterior para o padrão amarelo/azul da display."""
    nome = str(opcao or "").lower()
    cor = _normalizar_cor(valor)
    if not cor.startswith("#"):
        return valor

    if nome in _BORDER_OPTIONS:
        if cor in _DARK_BACKGROUND_MAP or cor in _ACCENT_MAP:
            return DISPLAY_YELLOW
        return valor

    if nome in _FOREGROUND_OPTIONS:
        if cor in _ACCENT_MAP:
            return DISPLAY_YELLOW
        if cor in _MUTED_FOREGROUND_MAP:
            return _MUTED_FOREGROUND_MAP[cor]
        return valor

    if nome in _BACKGROUND_OPTIONS:
        if cor in _DARK_BACKGROUND_MAP:
            return _DARK_BACKGROUND_MAP[cor]
        if cor in _ACCENT_MAP:
            return DISPLAY_YELLOW
        return valor

    return valor


def instalar_paleta_display() -> None:
    """Atualiza constantes usadas na construção das telas principais."""
    ODINView.COR_FUNDO_APP = DISPLAY_BLUE_DEEP
    ODINView.COR_TOPO = DISPLAY_BLUE
    ODINView.COR_CARD = DISPLAY_BLUE_DARK
    ODINView.COR_CARD_2 = DISPLAY_BLUE
    ODINView.COR_BORDA = DISPLAY_YELLOW
    ODINView.COR_TEXTO = DISPLAY_WHITE
    ODINView.COR_TEXTO_2 = DISPLAY_WHITE
    ODINView.COR_TEXTO_3 = DISPLAY_BLUE_LIGHT
    ODINView.COR_AZUL = DISPLAY_YELLOW
    ODINView.COR_AMARELO = DISPLAY_YELLOW
    ODINView.COR_NEUTRO = DISPLAY_BLUE_DARK

    RaspberryOperationWindow.COLOR_WAITING = DISPLAY_BLUE_DARK
    RaspberryOperationWindow.COLOR_POSITIONING = DISPLAY_BLUE
    RaspberryOperationWindow.COLOR_WAITING_REMOVAL = DISPLAY_BLUE_DEEP
    RaspberryOperationWindow.COLOR_PROCESSING = DISPLAY_YELLOW
    RaspberryOperationWindow.PREVIEW_BACKGROUND = DISPLAY_BLUE_DEEP
    RaspberryOperationWindow.PREVIEW_PANEL = DISPLAY_BLUE_DARK
    RaspberryOperationWindow.PREVIEW_BORDER = DISPLAY_YELLOW
    RaspberryOperationWindow.PREVIEW_GUIDE = DISPLAY_YELLOW
    RaspberryOperationWindow.PREVIEW_BOARD_GUIDE = DISPLAY_YELLOW
    RaspberryOperationWindow.PREVIEW_FAILED = DISPLAY_YELLOW
    RaspberryOperationWindow.PREVIEW_TEXT = DISPLAY_WHITE
    RaspberryOperationWindow.PREVIEW_MUTED = DISPLAY_BLUE_LIGHT

    # Classes derivadas redefinem algumas constantes. A importação tardia evita
    # dependência circular durante a inicialização do perfil final.
    try:
        from src.platform.raspberry_runtime_fixes import (
            StableRaspberryOperationWindow,
        )

        StableRaspberryOperationWindow.PREVIEW_FAILED = DISPLAY_YELLOW
    except Exception:
        pass

    try:
        from src.platform.blue_operation_window import (
            BlueRaspberryOperationWindow,
        )

        BlueRaspberryOperationWindow.PREVIEW_FAILED = DISPLAY_YELLOW
    except Exception:
        pass


def _texto_tematizado(texto: str) -> str:
    return (
        str(texto)
        .replace("CÍRCULO AZUL", "CÍRCULO AMARELO")
        .replace("Círculo azul", "Círculo amarelo")
        .replace("Marcados em azul", "Marcados em amarelo")
        .replace("marcados em azul", "marcados em amarelo")
    )


def _configurar(widget, **opcoes) -> None:
    if not opcoes:
        return
    try:
        widget.configure(**opcoes)
    except Exception:
        pass


def _obter(widget, opcao: str):
    try:
        return widget.cget(opcao)
    except Exception:
        return None


def _classe_widget(widget) -> str:
    try:
        return str(widget.winfo_class())
    except Exception:
        return type(widget).__name__


def _tematizar_itens_canvas(canvas) -> None:
    try:
        itens = canvas.find_all()
    except Exception:
        return

    for item in itens:
        for opcao in ("fill", "outline"):
            try:
                atual = canvas.itemcget(item, opcao)
            except Exception:
                continue
            novo = mapear_cor_display(
                "foreground" if opcao == "fill" else "highlightbackground",
                atual,
            )
            if novo == atual:
                novo = mapear_cor_display("background", atual)
            if novo != atual:
                try:
                    canvas.itemconfigure(item, **{opcao: novo})
                except Exception:
                    pass


def aplicar_tema_widget(widget) -> None:
    """Aplica a paleta a um widget Tk já existente, sem alterar cores OK/NG."""
    classe = _classe_widget(widget)
    alteracoes = {}

    for opcao in (
        "background",
        "foreground",
        "activebackground",
        "activeforeground",
        "highlightbackground",
        "highlightcolor",
        "insertbackground",
        "selectbackground",
        "selectforeground",
        "troughcolor",
        "selectcolor",
        "disabledforeground",
    ):
        atual = _obter(widget, opcao)
        if atual is None:
            continue
        novo = mapear_cor_display(opcao, atual)
        if novo != atual:
            alteracoes[opcao] = novo

    texto = _obter(widget, "text")
    if texto is not None:
        novo_texto = _texto_tematizado(str(texto))
        if novo_texto != str(texto):
            alteracoes["text"] = novo_texto

    if classe in {"Button", "Menubutton"}:
        alteracoes.update(
            background=DISPLAY_YELLOW,
            foreground=DISPLAY_INK,
            activebackground=DISPLAY_YELLOW_DARK,
            activeforeground=DISPLAY_INK,
            highlightbackground=DISPLAY_YELLOW,
        )
    elif classe in {"Checkbutton", "Radiobutton"}:
        alteracoes.update(
            background=DISPLAY_BLUE_DARK,
            foreground=DISPLAY_WHITE,
            activebackground=DISPLAY_BLUE_DARK,
            activeforeground=DISPLAY_YELLOW,
            selectcolor=DISPLAY_BLUE_DEEP,
        )
    elif classe in {"Entry", "Text", "Listbox", "Spinbox"}:
        alteracoes.update(
            background=DISPLAY_BLUE_DEEP,
            foreground=DISPLAY_WHITE,
            insertbackground=DISPLAY_YELLOW,
            selectbackground=DISPLAY_YELLOW,
            selectforeground=DISPLAY_INK,
        )

    _configurar(widget, **alteracoes)

    if classe == "Canvas":
        _tematizar_itens_canvas(widget)


def aplicar_tema_arvore(widget) -> None:
    aplicar_tema_widget(widget)
    try:
        filhos = tuple(widget.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        aplicar_tema_arvore(filho)


def configurar_estilos_ttk_display(root) -> None:
    try:
        style = ttk.Style(root)
    except Exception:
        return

    configuracoes = {
        "TFrame": {
            "background": DISPLAY_BLUE_DARK,
        },
        "TLabel": {
            "background": DISPLAY_BLUE_DARK,
            "foreground": DISPLAY_WHITE,
        },
        "TButton": {
            "background": DISPLAY_YELLOW,
            "foreground": DISPLAY_INK,
        },
        "TCheckbutton": {
            "background": DISPLAY_BLUE_DARK,
            "foreground": DISPLAY_WHITE,
        },
        "TRadiobutton": {
            "background": DISPLAY_BLUE_DARK,
            "foreground": DISPLAY_WHITE,
        },
        "TNotebook": {
            "background": DISPLAY_BLUE_DEEP,
            "bordercolor": DISPLAY_YELLOW,
        },
        "TNotebook.Tab": {
            "background": DISPLAY_BLUE,
            "foreground": DISPLAY_WHITE,
        },
        "Treeview": {
            "background": DISPLAY_BLUE_DEEP,
            "fieldbackground": DISPLAY_BLUE_DEEP,
            "foreground": DISPLAY_WHITE,
            "bordercolor": DISPLAY_YELLOW,
        },
        "Treeview.Heading": {
            "background": DISPLAY_BLUE,
            "foreground": DISPLAY_WHITE,
        },
        "TEntry": {
            "fieldbackground": DISPLAY_BLUE_DEEP,
            "foreground": DISPLAY_WHITE,
            "insertcolor": DISPLAY_YELLOW,
        },
        "TCombobox": {
            "fieldbackground": DISPLAY_BLUE_DEEP,
            "background": DISPLAY_BLUE,
            "foreground": DISPLAY_WHITE,
            "arrowcolor": DISPLAY_YELLOW,
        },
    }

    for nome, opcoes in configuracoes.items():
        try:
            style.configure(nome, **opcoes)
        except Exception:
            pass

    try:
        style.map(
            "TButton",
            background=[("active", DISPLAY_YELLOW_DARK)],
            foreground=[("active", DISPLAY_INK)],
        )
        style.map(
            "Treeview",
            background=[("selected", DISPLAY_YELLOW)],
            foreground=[("selected", DISPLAY_INK)],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", DISPLAY_YELLOW)],
            foreground=[("selected", DISPLAY_INK)],
        )
    except Exception:
        pass


class DisplayThemeMixin:
    """Tema exclusivo da branch display, aplicado à interface inteira."""

    def __init__(self, *args, **kwargs) -> None:
        self._display_theme_after_id = None
        instalar_paleta_display()
        super().__init__(*args, **kwargs)
        self._instalar_tema_display_runtime()

    def _instalar_tema_display_runtime(self) -> None:
        root = getattr(self, "root", None)
        if root is None:
            return

        try:
            root.option_add("*Background", DISPLAY_BLUE_DARK)
            root.option_add("*Foreground", DISPLAY_WHITE)
            root.option_add("*Button.background", DISPLAY_YELLOW)
            root.option_add("*Button.foreground", DISPLAY_INK)
            root.option_add("*Button.activeBackground", DISPLAY_YELLOW_DARK)
            root.option_add("*Button.activeForeground", DISPLAY_INK)
        except Exception:
            pass

        configurar_estilos_ttk_display(root)
        self._aplicar_tema_display_agora()

        try:
            root.bind_all("<Map>", self._evento_map_tema_display, add="+")
        except Exception:
            pass

        for atraso in (0, 120, 500):
            try:
                root.after(atraso, self._aplicar_tema_display_agora)
            except Exception:
                break

    def _evento_map_tema_display(self, _evento=None) -> None:
        root = getattr(self, "root", None)
        if root is None or self._display_theme_after_id is not None:
            return
        try:
            self._display_theme_after_id = root.after_idle(
                self._aplicar_tema_display_pendente
            )
        except Exception:
            self._display_theme_after_id = None

    def _aplicar_tema_display_pendente(self) -> None:
        self._display_theme_after_id = None
        self._aplicar_tema_display_agora()

    def _aplicar_tema_display_agora(self) -> None:
        root = getattr(self, "root", None)
        if root is None:
            return
        configurar_estilos_ttk_display(root)
        aplicar_tema_arvore(root)

    def _criar_interface_selecao_tela_cheia(self):
        janela, canvas = super()._criar_interface_selecao_tela_cheia()
        aplicar_tema_arvore(janela)
        try:
            janela.after_idle(lambda: aplicar_tema_arvore(janela))
        except Exception:
            pass
        return janela, canvas
