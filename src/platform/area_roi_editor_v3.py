from __future__ import annotations

import time

from src.platform.area_roi_editor_v2 import AreaRoiEditorV2Mixin


PREVIEW_DINAMICO_INTERVALO_S = 1.0 / 30.0


class AreaRoiEditorV3Mixin(AreaRoiEditorV2Mixin):
    """Mantém a lupa dinâmica sem codificar imagens em excesso durante o arrasto."""

    def __init__(self, *args, **kwargs) -> None:
        self._area_preview_ultimo_tempo_s = 0.0
        super().__init__(*args, **kwargs)

    def _atualizar_lupa_dinamica(self, evento) -> None:
        agora = time.perf_counter()
        operacao_finalizada = self._area_roi_mode is None

        if (
            not operacao_finalizada
            and agora - self._area_preview_ultimo_tempo_s
            < PREVIEW_DINAMICO_INTERVALO_S
        ):
            return

        self._area_preview_ultimo_tempo_s = agora
        super()._atualizar_lupa_dinamica(evento)
