from __future__ import annotations

import math

from src.platform.area_roi_editor import AreaRoiEditorMixin


HANDLE_HIT_PRECISO_PX = 9


class AreaRoiEditorV2Mixin(AreaRoiEditorMixin):
    """Ajusta a área de clique das alças para não bloquear ROIs próximas."""

    def _handle_atingido_area(
        self,
        canvas_x: int,
        canvas_y: int,
    ) -> str | None:
        melhor = None
        menor_distancia = None

        for nome, (handle_x, handle_y) in self._handles_canvas().items():
            distancia = math.hypot(
                float(canvas_x) - handle_x,
                float(canvas_y) - handle_y,
            )
            if distancia > HANDLE_HIT_PRECISO_PX:
                continue
            if menor_distancia is None or distancia < menor_distancia:
                melhor = nome
                menor_distancia = distancia

        return melhor
