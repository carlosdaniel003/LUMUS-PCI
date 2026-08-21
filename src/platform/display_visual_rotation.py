from __future__ import annotations

from src.ui.main_window_parts.image.rotacao_visual_principal import (
    normalizar_rotacao_visual,
    rotacionar_imagem_visual,
)


def obter_rotacao_visual_display(view) -> int:
    """Lê a orientação visual atual da tela principal sem alterar a câmera."""
    return normalizar_rotacao_visual(
        getattr(view, "rotacao_visual_principal", 0)
    )


def preparar_frame_visual_display(frame, rotacao: int):
    """Retorna somente a representação visual usada pelo F3.

    O frame de origem nunca é modificado. A rotação segue exatamente a mesma
    convenção da imagem principal do ODIN (0/90/180/270 graus).
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame
    return rotacionar_imagem_visual(
        frame,
        normalizar_rotacao_visual(rotacao),
    )
