from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.platform.display_settings_ux import (
    aplicar_ux_configuracoes_display,
)


_PATCH_OPEN = "_odin_display_settings_fullscreen_estavel"

_SECTION_TITLES = {
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


def calcular_margem_responsiva(largura: int) -> int:
    """Retorna uma margem segura sem comprimir os controles."""
    largura = max(0, int(largura))
    if largura < 1100:
        return 14
    if largura < 1500:
        return 24
    return min(72, max(32, int((largura - 1500) / 8)))


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


def _ativar_tela_cheia(janela) -> None:
    if getattr(janela, "_display_settings_fullscreen_active", False):
        return

    try:
        janela.overrideredirect(False)
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
        estilo.configure(
            "Odin.TNotebook",
            background=cores.DISPLAY_DARK,
            borderwidth=0,
            relief="flat",
            tabmargins=(0, 0, 0, 6),
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
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
            foreground=[
                ("selected", cores.DISPLAY_INK),
                ("active", cores.DISPLAY_WHITE),
            ],
            lightcolor=[
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
            darkcolor=[
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
            bordercolor=[
                ("selected", cores.DISPLAY_YELLOW_DARK),
                ("active", cores.DISPLAY_DARK_HOVER),
            ],
        )
        notebook.configure(style="Odin.TNotebook", takefocus=True)
    except Exception:
        pass


def _card_da_label(label):
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


def _ocultar_faixa_original(card) -> None:
    if getattr(card, "_display_settings_stripe_hidden", False):
        return
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
                _configurar(filho, height=1)
            break

    card._display_settings_stripe_hidden = True


def _estilizar_cards(janela, cores) -> None:
    processados = set()
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Label):
            continue
        titulo = _texto(widget)
        if titulo not in _SECTION_TITLES:
            continue

        card = _card_da_label(widget)
        if card is None or card in processados:
            continue
        processados.add(card)

        _ocultar_faixa_original(card)
        _configurar(
            card,
            background=cores.DISPLAY_DARK_RAISED,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
        )
        try:
            card.pack_configure(fill=tk.X, padx=(0, 8), pady=(0, 12))
        except Exception:
            pass

        _configurar(
            widget,
            foreground=cores.DISPLAY_WHITE,
            background=cores.DISPLAY_DARK_RAISED,
            font=("Segoe UI", 11, "bold"),
        )
        try:
            widget.pack_configure(padx=16, pady=(14, 6))
        except Exception:
            pass

        for descendente in _percorrer_widgets(card):
            if descendente is card:
                continue
            classe = _classe(descendente)
            if classe in {
                "Frame",
                "Label",
                "Checkbutton",
                "Radiobutton",
                "Scale",
            }:
                _configurar(descendente, background=cores.DISPLAY_DARK_RAISED)

            if isinstance(descendente, tk.Label) and descendente is not widget:
                texto = _texto(descendente)
                if texto and texto not in _SECTION_TITLES:
                    try:
                        fonte = str(descendente.cget("font"))
                    except Exception:
                        fonte = ""
                    if "bold" not in fonte.lower():
                        _configurar(descendente, foreground=cores.DISPLAY_MUTED)


def _estilizar_cabecalho(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        texto = _texto(widget)
        if isinstance(widget, tk.Label) and texto == "Configurações do sistema":
            _configurar(
                widget,
                foreground=cores.DISPLAY_WHITE,
                font=("Segoe UI", 18, "bold"),
            )
        elif isinstance(widget, tk.Label) and texto.startswith("Ajuste referências"):
            _configurar(widget, foreground=cores.DISPLAY_MUTED)
        elif texto == "ODIN":
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_YELLOW,
                highlightthickness=0,
                bd=0,
            )
        elif texto == "✕":
            _configurar(
                widget,
                background=cores.DISPLAY_DANGER_DARK,
                foreground=cores.DISPLAY_DANGER_LIGHT,
                activebackground=cores.DISPLAY_DANGER,
                activeforeground=cores.DISPLAY_WHITE,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
            )


def _estilizar_botoes(janela, cores) -> None:
    primarios = {"Salvar", "Salvar LEDs"}
    perigos = {"Ref. apagado", "Restaurar padrões da câmera"}
    sucessos = {"Ref. aceso"}
    informativos = {"Carregar refs."}
    selecao = {"Configurar LEDs"}

    for widget in _percorrer_widgets(janela):
        if _classe(widget) not in {"Button", "Menubutton"}:
            continue
        texto = _texto(widget)

        estilo = {
            "background": cores.DISPLAY_DARK_CARD,
            "foreground": cores.DISPLAY_WHITE,
            "activebackground": cores.DISPLAY_DARK_HOVER,
            "activeforeground": cores.DISPLAY_WHITE,
        }
        if texto in primarios:
            estilo.update(
                background=cores.DISPLAY_YELLOW_DARK,
                foreground=cores.DISPLAY_INK,
                activebackground=cores.DISPLAY_YELLOW,
                activeforeground=cores.DISPLAY_INK,
            )
        elif texto in perigos:
            estilo.update(
                foreground=cores.DISPLAY_DANGER_LIGHT,
                activebackground=cores.DISPLAY_DANGER_DARK,
                activeforeground=cores.DISPLAY_DANGER_LIGHT,
            )
        elif texto in sucessos:
            estilo.update(
                foreground=cores.DISPLAY_SUCCESS_LIGHT,
                activebackground=cores.DISPLAY_SUCCESS_DARK,
                activeforeground=cores.DISPLAY_SUCCESS_LIGHT,
            )
        elif texto in informativos:
            estilo.update(
                foreground=cores.DISPLAY_BLUE_LIGHT,
                activebackground=cores.DISPLAY_BLUE_DARK,
                activeforeground=cores.DISPLAY_BLUE_LIGHT,
            )
        elif texto in selecao:
            estilo.update(
                foreground=cores.DISPLAY_PURPLE_LIGHT,
                activebackground=cores.DISPLAY_PURPLE_DARK,
                activeforeground=cores.DISPLAY_PURPLE_LIGHT,
            )
        elif texto in {"Cancelar", "Fechar"}:
            estilo.update(
                background=cores.DISPLAY_DARK_RAISED,
                foreground=cores.DISPLAY_WHITE,
            )

        _configurar(
            widget,
            **estilo,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=16,
            pady=8,
        )


def _estilizar_campos_e_controles(janela, cores) -> None:
    for widget in _percorrer_widgets(janela):
        classe = _classe(widget)
        if classe in {"Frame", "Canvas", "LabelFrame"}:
            _configurar(
                widget,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
            )
        elif classe in {"Entry", "Spinbox", "Text", "Listbox"}:
            _configurar(
                widget,
                background=cores.DISPLAY_DARK,
                foreground=cores.DISPLAY_WHITE,
                insertbackground=cores.DISPLAY_YELLOW,
                selectbackground=cores.DISPLAY_BLUE_DARK,
                selectforeground=cores.DISPLAY_WHITE,
                highlightbackground=cores.DISPLAY_BORDER,
                highlightcolor=cores.DISPLAY_YELLOW_DARK,
                highlightthickness=1,
                bd=0,
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
                highlightthickness=0,
            )
        elif isinstance(widget, tk.Scrollbar):
            _configurar(
                widget,
                background=cores.DISPLAY_DARK_RAISED,
                activebackground=cores.DISPLAY_YELLOW_DARK,
                troughcolor=cores.DISPLAY_DARK,
                highlightthickness=0,
                bd=0,
                relief=tk.FLAT,
                elementborderwidth=0,
                width=12,
                cursor="hand2",
            )


def _ajustar_linhas_de_controle(janela) -> None:
    """Preserva o pack original e ajusta apenas espaçamento e expansão."""
    processados = set()
    for widget in _percorrer_widgets(janela):
        if _classe(widget) != "Scale":
            continue
        ajuste = getattr(widget, "master", None)
        linha = getattr(ajuste, "master", None)
        if linha is None or linha in processados:
            continue
        processados.add(linha)

        try:
            linha.pack_configure(fill=tk.X, expand=True, padx=18, pady=(7, 12))
        except Exception:
            pass
        try:
            ajuste.pack_configure(fill=tk.X, pady=(4, 0))
        except Exception:
            pass
        try:
            widget.pack_configure(side=tk.LEFT, fill=tk.X, expand=True)
        except Exception:
            pass


def _estilizar_rodape(janela, cores) -> None:
    texto_ajuda = (
        "As alterações só são aplicadas ao salvar.  •  "
        "Roda do mouse: navegar  •  Ctrl+1/2: abas  •  "
        "Ctrl+Enter: salvar  •  Esc: fechar"
    )
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Label):
            continue
        if not _texto(widget).startswith("As alterações"):
            continue
        _configurar(
            widget,
            text=texto_ajuda,
            foreground=cores.DISPLAY_MUTED,
            background=cores.DISPLAY_DARK_ALT,
            wraplength=760,
            justify=tk.LEFT,
        )
        frame = getattr(widget, "master", None)
        if frame is not None:
            _configurar(frame, background=cores.DISPLAY_DARK_ALT)
        break


def _instalar_margem_responsiva(janela) -> None:
    if getattr(janela, "_display_settings_responsive_bound", False):
        return

    try:
        frame_raiz = tuple(janela.winfo_children())[0]
    except Exception:
        frame_raiz = None

    def atualizar(evento=None):
        if frame_raiz is None:
            return
        largura = getattr(evento, "width", None)
        if largura is None:
            try:
                largura = janela.winfo_width()
            except Exception:
                largura = 1200
        margem = calcular_margem_responsiva(largura)
        if getattr(janela, "_display_settings_last_margin", None) == margem:
            return
        janela._display_settings_last_margin = margem
        try:
            frame_raiz.pack_configure(padx=margem, pady=18)
        except Exception:
            pass

    janela.bind("<Configure>", atualizar, add="+")
    janela._display_settings_responsive_bound = True
    atualizar()


def aplicar_configuracoes_fullscreen(view, janela) -> None:
    """Aplica fullscreen e visual estável sem trocar gerenciadores de layout."""
    if janela is None:
        return

    from src.platform import display_theme as cores

    _ativar_tela_cheia(janela)
    aplicar_ux_configuracoes_display(view, janela)
    _configurar(janela, background=cores.DISPLAY_DARK)
    _estilizar_notebook(janela, _notebook(janela), cores)
    _estilizar_cabecalho(janela, cores)
    _estilizar_cards(janela, cores)
    _estilizar_botoes(janela, cores)
    _estilizar_campos_e_controles(janela, cores)
    _ajustar_linhas_de_controle(janela)
    _estilizar_rodape(janela, cores)
    _instalar_margem_responsiva(janela)

    for canvas in _canvases_rolagem(janela):
        _configurar(
            canvas,
            background=cores.DISPLAY_DARK,
            highlightthickness=0,
            bd=0,
        )
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    try:
        janela.update_idletasks()
    except Exception:
        pass


def instalar_configuracoes_fullscreen_display() -> None:
    """Instala uma única camada estável sobre a abertura das configurações."""
    from src.ui.main_window import ODINView

    original = ODINView.abrir_janela_configuracoes
    if getattr(original, _PATCH_OPEN, False):
        return

    def abrir_fullscreen(self, *args, **kwargs):
        try:
            anteriores = tuple(self.root.winfo_children())
        except Exception:
            anteriores = ()

        retorno = original(self, *args, **kwargs)
        janela = _encontrar_janela(self.root, anteriores)
        aplicar_configuracoes_fullscreen(self, janela)

        if janela is not None:
            # Uma única reaplicação tardia é suficiente para vencer o Map do
            # tema global sem gerar ciclos de Configure/Map ou event storm.
            try:
                janela.after(
                    120,
                    lambda j=janela, v=self: aplicar_configuracoes_fullscreen(v, j),
                )
            except Exception:
                pass

        return retorno

    setattr(abrir_fullscreen, _PATCH_OPEN, True)
    setattr(abrir_fullscreen, "_odin_original", original)
    ODINView.abrir_janela_configuracoes = abrir_fullscreen
