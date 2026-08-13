from __future__ import annotations

import tkinter as tk


_ROI_TOOLBAR_TEXTS = {
    "▰ segmento",
    "● circulo",
    "✎ segmento por pontos",
    "▣ selecao em massa",
}

_PATCH_ROI_TOOLBAR_THEME = False


def _normalizar_texto_ferramenta(texto: str) -> str:
    import unicodedata

    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    normalizado = "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )
    return " ".join(normalizado.lower().split())


def eh_botao_ferramenta_roi(texto: str) -> bool:
    return _normalizar_texto_ferramenta(texto) in _ROI_TOOLBAR_TEXTS


def instalar_preservacao_estado_toolbar_roi() -> None:
    """Impede o tema global de apagar o destaque persistente da ferramenta ativa.

    Os botões da toolbar de ROI já controlam diretamente background/foreground para
    representar o estado selecionado. O tema global não deve classificá-los como
    botões neutros nem instalar hover que restaure uma cor escura ao sair o mouse.
    """

    global _PATCH_ROI_TOOLBAR_THEME
    if _PATCH_ROI_TOOLBAR_THEME:
        return

    import src.platform.display_theme as display_theme

    original = display_theme._aplicar_estilo_botao
    if getattr(original, "_odin_preserva_toolbar_roi", False):
        _PATCH_ROI_TOOLBAR_THEME = True
        return

    def aplicar_estilo_botao_preservando_toolbar(widget, texto: str) -> None:
        if eh_botao_ferramenta_roi(texto):
            # Preserva bg/fg/activebackground definidos pelo editor. Assim o
            # amarelo representa seleção persistente, e não apenas o estado
            # momentâneo de clique/hover.
            display_theme._configurar(
                widget,
                highlightbackground=display_theme.DISPLAY_BORDER,
                highlightcolor=display_theme.DISPLAY_YELLOW_DARK,
                highlightthickness=1,
                relief=tk.FLAT,
                bd=0,
            )
            return
        original(widget, texto)

    aplicar_estilo_botao_preservando_toolbar._odin_preserva_toolbar_roi = True
    aplicar_estilo_botao_preservando_toolbar._odin_original = original
    display_theme._aplicar_estilo_botao = aplicar_estilo_botao_preservando_toolbar
    _PATCH_ROI_TOOLBAR_THEME = True
