from __future__ import annotations

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    normalizar_tipo_roi,
    pontos_segmento,
)
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    obter_ponto_visual_view,
)


def ponto_original_para_canvas(self, x: float, y: float) -> tuple[float, float]:
    vx, vy = obter_ponto_visual_view(self, x, y)
    return (
        float(self.deslocamento_imagem_x) + float(vx) * float(self.escala_exibicao),
        float(self.deslocamento_imagem_y) + float(vy) * float(self.escala_exibicao),
    )


def pontos_segmento_canvas(self, alvo, escala_forma: float = 1.0) -> list[float]:
    coordenadas = []
    for x, y in pontos_segmento(alvo, escala=escala_forma):
        cx, cy = ponto_original_para_canvas(self, float(x), float(y))
        coordenadas.extend((cx, cy))
    return coordenadas


def desenhar_forma_roi_canvas(
    self,
    alvo,
    cor: str,
    largura_linha: int = 2,
    dash=None,
    tags=(),
    escala_forma: float = 1.0,
):
    if normalizar_tipo_roi(getattr(alvo, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        return self.canvas.create_polygon(
            *pontos_segmento_canvas(self, alvo, escala_forma=escala_forma),
            fill="",
            outline=cor,
            width=int(largura_linha),
            dash=dash,
            tags=tags,
        )

    centro_x, centro_y = ponto_original_para_canvas(
        self,
        getattr(alvo, "centro_x", 0),
        getattr(alvo, "centro_y", 0),
    )
    raio = max(
        3,
        int(round(float(getattr(alvo, "raio", 1)) * float(escala_forma) * float(self.escala_exibicao))),
    )
    return self.canvas.create_oval(
        centro_x - raio,
        centro_y - raio,
        centro_x + raio,
        centro_y + raio,
        outline=cor,
        width=int(largura_linha),
        dash=dash,
        tags=tags,
    )
