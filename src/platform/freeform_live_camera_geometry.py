from __future__ import annotations

from src.platform.segment_project_geometry_persistence import (
    copiar_lista_geometria_completa,
)


class FreeformLiveCameraGeometryMixin:
    """Impede o refresh legado da câmera de desenhar ROIs livres como círculos.

    O ``ODINApp`` histórico reconstrói ``leds_selecionados`` a partir de
    ``leds_manuais_camera`` usando apenas id/centro/raio a cada frame. Essa
    cópia reduzida perde ``tipo_roi`` e ``pontos_segmento_livre`` antes do
    redraw e das previews auxiliares. Esta camada mantém a geometria manual
    canônica durante todo o refresh, inclusive no primeiro desenho do frame.
    """

    def _freeform_camera_manual_snapshot(self):
        if not bool(getattr(self, "camera_ativa", False)):
            return []
        if bool(getattr(self, "camera_em_pausa_analise", False)):
            return []
        return copiar_lista_geometria_completa(
            getattr(self, "leds_manuais_camera", ())
        )

    def atualizar_frame_camera(self):
        snapshot = self._freeform_camera_manual_snapshot()
        if not snapshot:
            return super().atualizar_frame_camera()

        view = getattr(self, "view", None)
        desenhar_original = getattr(view, "desenhar_canvas", None)
        if not callable(desenhar_original):
            return super().atualizar_frame_camera()

        ids_snapshot = tuple(str(led.id) for led in snapshot)

        def desenhar_sem_degradar_geometria(leds, resultados, *args, **kwargs):
            ids_recebidos = tuple(
                str(getattr(led, "id", ""))
                for led in (leds or ())
            )
            usando_selecao_manual = bool(
                getattr(self, "selecao_manual_camera_ativa", False)
                or str(getattr(self, "modo_atual", "")) == "selecionar_leds_camera"
            )
            if usando_selecao_manual and ids_recebidos == ids_snapshot:
                completos = copiar_lista_geometria_completa(snapshot)
                self.leds_manuais_camera = copiar_lista_geometria_completa(snapshot)
                self.leds_selecionados = completos
                return desenhar_original(
                    completos,
                    resultados,
                    *args,
                    **kwargs,
                )
            return desenhar_original(
                leds,
                resultados,
                *args,
                **kwargs,
            )

        view.desenhar_canvas = desenhar_sem_degradar_geometria
        try:
            resultado = super().atualizar_frame_camera()
        finally:
            view.desenhar_canvas = desenhar_original

        # O estado interno também precisa permanecer completo. Assim o botão de
        # salvar nunca encontra a janela de alguns milissegundos em que o app
        # legado havia reduzido a seleção a círculos.
        if bool(getattr(self, "selecao_manual_camera_ativa", False)) or str(
            getattr(self, "modo_atual", "")
        ) == "selecionar_leds_camera":
            self.leds_manuais_camera = copiar_lista_geometria_completa(snapshot)
            self.leds_selecionados = copiar_lista_geometria_completa(snapshot)

        return resultado
