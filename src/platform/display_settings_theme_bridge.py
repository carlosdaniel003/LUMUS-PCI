from __future__ import annotations

import tkinter as tk

from src.platform.display_settings_ux import (
    aplicar_ux_configuracoes_display,
)
from src.platform.display_theme import DisplayThemeMixin


_PATCH_MARKER = "_odin_display_settings_theme_bridge"


def _janelas_configuracoes(root):
    try:
        filhos = tuple(root.winfo_children())
    except Exception:
        filhos = ()

    for widget in filhos:
        if not isinstance(widget, tk.Toplevel):
            continue
        try:
            if widget.winfo_exists() and str(widget.title()) == "Configurações - ODIN":
                yield widget
        except Exception:
            continue


def instalar_ponte_tema_configuracoes() -> None:
    """Reaplica a UX específica depois do tema global processar um Map."""
    original = DisplayThemeMixin._aplicar_tema_display_agora
    if getattr(original, _PATCH_MARKER, False):
        return

    def aplicar_tema_e_configuracoes(self):
        retorno = original(self)
        root = getattr(self, "root", None)
        if root is None:
            return retorno

        view = getattr(self, "view", None)
        for janela in _janelas_configuracoes(root):
            aplicar_ux_configuracoes_display(view, janela)
        return retorno

    setattr(aplicar_tema_e_configuracoes, _PATCH_MARKER, True)
    setattr(aplicar_tema_e_configuracoes, "_odin_original", original)
    DisplayThemeMixin._aplicar_tema_display_agora = aplicar_tema_e_configuracoes
