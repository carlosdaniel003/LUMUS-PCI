from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.ui.main_window_parts.settings.abrir_janela_configuracoes import (
    abrir_janela_configuracoes as abrir_janela_configuracoes_base,
)


def _percorrer_widgets(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from _percorrer_widgets(filho)


def _abrir_lista_combobox(evento) -> str:
    combo = evento.widget

    try:
        if combo.instate(("disabled",)):
            return "break"
    except tk.TclError:
        return "break"

    combo.focus_set()

    try:
        combo.tk.call("ttk::combobox::Post", str(combo))
    except tk.TclError:
        try:
            combo.event_generate("<Alt-Down>")
        except tk.TclError:
            pass

    return "break"


def _configurar_comboboxes(janela: tk.Toplevel) -> None:
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, ttk.Combobox):
            continue

        try:
            quantidade_opcoes = len(widget.cget("values"))
            widget.configure(
                takefocus=True,
                cursor="hand2",
                height=max(4, min(10, quantidade_opcoes)),
            )
        except tk.TclError:
            pass

        widget.bind(
            "<Button-1>",
            _abrir_lista_combobox,
        )
        widget.bind(
            "<Return>",
            _abrir_lista_combobox,
        )
        widget.bind(
            "<space>",
            _abrir_lista_combobox,
        )


def abrir_janela_configuracoes(self, *args, **kwargs) -> None:
    janelas_antes = {
        widget
        for widget in self.root.winfo_children()
        if isinstance(widget, tk.Toplevel)
    }

    abrir_janela_configuracoes_base(
        self,
        *args,
        **kwargs,
    )

    novas_janelas = [
        widget
        for widget in self.root.winfo_children()
        if isinstance(widget, tk.Toplevel)
        and widget not in janelas_antes
        and widget.winfo_exists()
    ]

    if not novas_janelas:
        return

    janela = novas_janelas[-1]

    # O grab era aplicado enquanto a janela ainda estava oculta. No Raspberry
    # isso podia impedir o pop-up nativo do Combobox de receber o clique.
    try:
        janela.grab_release()
    except tk.TclError:
        pass

    janela.update_idletasks()
    _configurar_comboboxes(janela)
    janela.lift()
    janela.focus_force()
