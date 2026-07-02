from __future__ import annotations

import importlib

from src.ui.main_window_parts.settings.abrir_janela_configuracoes import (
    abrir_janela_configuracoes as abrir_janela_configuracoes_base,
)
from src.ui.main_window_parts.widgets.select_lista import SelectLista


_MODULO_CONFIGURACOES = importlib.import_module(
    "src.ui.main_window_parts.settings.abrir_janela_configuracoes"
)


def abrir_janela_configuracoes(self, *args, **kwargs) -> None:
    """Abre configurações substituindo somente os selects ttk problemáticos."""

    combobox_original = _MODULO_CONFIGURACOES.ttk.Combobox
    _MODULO_CONFIGURACOES.ttk.Combobox = SelectLista

    try:
        abrir_janela_configuracoes_base(
            self,
            *args,
            **kwargs,
        )
    finally:
        _MODULO_CONFIGURACOES.ttk.Combobox = combobox_original
