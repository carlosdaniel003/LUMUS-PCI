from __future__ import annotations

import tkinter as tk


_PATCH_TOOLBAR_RESPONSIVA = False


PERFIL_TOOLBAR_COMPACTO = {
    "nome": "compacto",
    "colunas": 2,
    "fonte": 9,
    "padx": 10,
    "pady": 7,
}
PERFIL_TOOLBAR_NOTEBOOK = {
    "nome": "notebook",
    "colunas": 4,
    "fonte": 10,
    "padx": 14,
    "pady": 7,
}
PERFIL_TOOLBAR_AMPLA = {
    "nome": "amplo",
    "colunas": 4,
    "fonte": 11,
    "padx": 20,
    "pady": 9,
}


def calcular_perfil_toolbar_roi(largura: int) -> dict:
    """Retorna dimensões da toolbar adequadas à largura real da tela."""
    largura = max(1, int(largura or 1))
    if largura >= 1700:
        return dict(PERFIL_TOOLBAR_AMPLA)
    if largura >= 1050:
        return dict(PERFIL_TOOLBAR_NOTEBOOK)
    return dict(PERFIL_TOOLBAR_COMPACTO)


def _widgets_ferramenta(app) -> list:
    nomes = (
        "_botao_tipo_roi_segmento",
        "_botao_tipo_roi_circulo",
        "_botao_tipo_roi_segmento_livre",
        "_botao_selecao_massa",
    )
    return [
        widget
        for widget in (getattr(app, nome, None) for nome in nomes)
        if widget is not None
    ]


def _esquecer_geometria(widget) -> None:
    if widget is None:
        return
    try:
        manager = str(widget.winfo_manager() or "")
    except Exception:
        manager = ""
    try:
        if manager == "pack":
            widget.pack_forget()
        elif manager == "grid":
            widget.grid_forget()
        elif manager == "place":
            widget.place_forget()
    except Exception:
        pass


def _localizar_textos_barra(barra, seletor, zoom_frame):
    try:
        filhos = list(barra.winfo_children())
    except Exception:
        return None, None

    botao_ok = None
    textos = None
    for filho in filhos:
        if filho is seletor or filho is zoom_frame:
            continue
        try:
            if isinstance(filho, tk.Button) and str(filho.cget("text")) == "OK":
                botao_ok = filho
                continue
        except Exception:
            pass
        try:
            if isinstance(filho, tk.Frame):
                textos = filho
        except Exception:
            pass
    return textos, botao_ok


def _ajustar_textos_cabecalho(textos, largura: int, perfil: dict) -> None:
    if textos is None:
        return
    try:
        labels = [
            filho
            for filho in textos.winfo_children()
            if isinstance(filho, tk.Label)
        ]
    except Exception:
        return

    if labels:
        try:
            titulo_fonte = 14 if perfil["nome"] == "amplo" else 12
            labels[0].configure(font=("DejaVu Sans", titulo_fonte, "bold"))
        except Exception:
            pass
    if len(labels) > 1:
        try:
            wrap = max(420, min(1250, int(largura) - 220))
            labels[1].configure(
                wraplength=wrap,
                justify=tk.LEFT,
            )
        except Exception:
            pass


def _aplicar_layout_toolbar_roi(app, janela) -> None:
    botoes = _widgets_ferramenta(app)
    if not botoes:
        return

    primeiro = botoes[0]
    try:
        frame_botoes = primeiro.master
        seletor = frame_botoes.master
        barra = seletor.master
    except Exception:
        return

    zoom_label = getattr(app, "_label_zoom_selecao", None)
    zoom_frame = getattr(zoom_label, "master", None)
    textos, botao_ok = _localizar_textos_barra(
        barra,
        seletor,
        zoom_frame,
    )

    try:
        largura = int(janela.winfo_width())
        if largura <= 1:
            largura = int(janela.winfo_screenwidth())
    except Exception:
        largura = 1280
    perfil = calcular_perfil_toolbar_roi(largura)

    # Remove a altura fixa original de 66 px. A barra passa a crescer somente
    # quando necessário, evitando comprimir os botões em notebooks.
    try:
        barra.pack_propagate(True)
    except Exception:
        pass
    try:
        barra.grid_propagate(True)
        barra.configure(height=1)
    except Exception:
        pass

    # Cabeçalho em duas faixas: título/OK em cima e ferramentas/zoom embaixo.
    # Isso impede que o texto de ajuda dispute largura com Segmento/Círculo.
    for widget in (textos, botao_ok, seletor, zoom_frame):
        _esquecer_geometria(widget)

    try:
        barra.grid_columnconfigure(0, weight=1)
        barra.grid_columnconfigure(1, weight=0)
    except Exception:
        pass

    if textos is not None:
        try:
            textos.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(18, 8),
                pady=(7, 2),
            )
        except Exception:
            pass
    if botao_ok is not None:
        try:
            botao_ok.configure(
                font=("DejaVu Sans", 11 if perfil["nome"] == "amplo" else 10, "bold"),
                padx=28 if perfil["nome"] == "amplo" else 22,
                pady=9 if perfil["nome"] == "amplo" else 7,
            )
            botao_ok.grid(
                row=0,
                column=1,
                sticky="e",
                padx=(8, 18),
                pady=(7, 2),
            )
        except Exception:
            pass
    if seletor is not None:
        try:
            seletor.grid(
                row=1,
                column=0,
                sticky="ew",
                padx=(18, 8),
                pady=(2, 8),
            )
        except Exception:
            pass
    if zoom_frame is not None:
        try:
            zoom_frame.grid(
                row=1,
                column=1,
                sticky="e",
                padx=(8, 18),
                pady=(2, 8),
            )
        except Exception:
            pass

    _ajustar_textos_cabecalho(textos, largura, perfil)

    # Os botões deixam de ter tamanho definido apenas pelo texto e passam a
    # dividir igualmente o espaço disponível. Em telas realmente estreitas,
    # reorganizam-se automaticamente em duas colunas.
    try:
        frame_botoes.pack_configure(fill=tk.X, expand=True)
    except Exception:
        pass
    for botao in botoes:
        _esquecer_geometria(botao)

    colunas = int(perfil["colunas"])
    for coluna in range(4):
        try:
            frame_botoes.grid_columnconfigure(
                coluna,
                weight=1 if coluna < colunas else 0,
                uniform="ferramentas_roi" if coluna < colunas else "",
            )
        except Exception:
            pass

    for indice, botao in enumerate(botoes):
        linha = indice // colunas
        coluna = indice % colunas
        try:
            botao.configure(
                font=("DejaVu Sans", int(perfil["fonte"]), "bold"),
                padx=int(perfil["padx"]),
                pady=int(perfil["pady"]),
            )
            botao.grid(
                row=linha,
                column=coluna,
                sticky="nsew",
                padx=3,
                pady=3,
            )
        except Exception:
            pass

    try:
        setattr(app, "_odin_toolbar_roi_perfil", perfil["nome"])
    except Exception:
        pass


def _agendar_layout_toolbar_roi(app, janela, atraso_ms: int = 35) -> None:
    pendente = getattr(app, "_odin_toolbar_roi_after_id", None)
    if pendente is not None:
        try:
            janela.after_cancel(pendente)
        except Exception:
            pass

    def aplicar() -> None:
        try:
            app._odin_toolbar_roi_after_id = None
        except Exception:
            pass
        _aplicar_layout_toolbar_roi(app, janela)

    try:
        app._odin_toolbar_roi_after_id = janela.after(
            max(0, int(atraso_ms)),
            aplicar,
        )
    except Exception:
        aplicar()


def instalar_toolbar_selecao_led_responsiva() -> None:
    """Torna responsiva a toolbar criada por FullscreenLedSelectionMixin."""
    global _PATCH_TOOLBAR_RESPONSIVA
    if _PATCH_TOOLBAR_RESPONSIVA:
        return

    from src.platform.fullscreen_led_selection import FullscreenLedSelectionMixin

    original = FullscreenLedSelectionMixin._criar_interface_selecao_tela_cheia
    if getattr(original, "_odin_toolbar_responsiva", False):
        _PATCH_TOOLBAR_RESPONSIVA = True
        return

    def criar_interface_responsiva(self, *args, **kwargs):
        janela, canvas = original(self, *args, **kwargs)

        # O callback roda depois que os mixins de Segmento por pontos e Seleção
        # em massa terminarem de acrescentar seus próprios botões.
        try:
            janela.after_idle(
                lambda: _agendar_layout_toolbar_roi(self, janela, 0)
            )
        except Exception:
            _agendar_layout_toolbar_roi(self, janela, 0)

        def ao_redimensionar(evento=None):
            if evento is not None and getattr(evento, "widget", janela) is not janela:
                return
            _agendar_layout_toolbar_roi(self, janela)

        try:
            janela.bind("<Configure>", ao_redimensionar, add="+")
        except Exception:
            pass
        return janela, canvas

    criar_interface_responsiva._odin_toolbar_responsiva = True
    criar_interface_responsiva._odin_original = original
    FullscreenLedSelectionMixin._criar_interface_selecao_tela_cheia = (
        criar_interface_responsiva
    )
    _PATCH_TOOLBAR_RESPONSIVA = True
