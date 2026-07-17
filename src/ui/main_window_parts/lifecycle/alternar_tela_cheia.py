from __future__ import annotations

import tkinter as tk

from src.ui.main_window_parts.lifecycle.obter_geometria_monitor_atual import (
    formatar_geometria_janela,
)


REFORCO_TELA_CHEIA_MS = 450


def _aplicar_tela_cheia_nativa(self) -> None:
    """Solicita fullscreen ao gerenciador de janelas, escondendo barras do sistema."""
    if not bool(getattr(self, "tela_cheia_ativa", False)):
        return

    try:
        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)
        self.root.attributes("-fullscreen", True)
        self.root.update_idletasks()
        self.root.lift()
        self.root.focus_force()
    except tk.TclError:
        return


def _agendar_reforco_tela_cheia(self) -> None:
    """Reaplica fullscreen após o gerenciador Linux terminar de mapear a janela."""
    after_anterior = getattr(self, "_reforco_tela_cheia_after_id", None)
    if after_anterior is not None:
        try:
            self.root.after_cancel(after_anterior)
        except tk.TclError:
            pass

    try:
        self._reforco_tela_cheia_after_id = self.root.after(
            REFORCO_TELA_CHEIA_MS,
            lambda: _finalizar_reforco_tela_cheia(self),
        )
    except tk.TclError:
        self._reforco_tela_cheia_after_id = None


def _finalizar_reforco_tela_cheia(self) -> None:
    self._reforco_tela_cheia_after_id = None
    _aplicar_tela_cheia_nativa(self)


def alternar_tela_cheia(self, evento=None):
    if self.tela_cheia_ativa:
        self.sair_tela_cheia(evento)
        return "break"

    geometria_monitor = self.obter_geometria_monitor_atual()
    geometria_tela_cheia = formatar_geometria_janela(
        largura_janela=geometria_monitor["monitor_largura"],
        altura_janela=geometria_monitor["monitor_altura"],
        posicao_x=geometria_monitor["monitor_x"],
        posicao_y=geometria_monitor["monitor_y"],
    )

    try:
        # Primeiro posiciona a janela no monitor correto. Depois solicita o modo
        # fullscreen nativo ao gerenciador de janelas, que também oculta a barra
        # superior e a barra de tarefas no Linux.
        self.root.attributes("-fullscreen", False)
        self.root.attributes("-topmost", False)
        self.root.overrideredirect(False)
        self.root.state("normal")
        self.root.geometry(geometria_tela_cheia)
        self.root.update_idletasks()

        self.tela_cheia_ativa = True
        _aplicar_tela_cheia_nativa(self)
        _agendar_reforco_tela_cheia(self)
    except tk.TclError:
        self.tela_cheia_ativa = False

    return "break"
