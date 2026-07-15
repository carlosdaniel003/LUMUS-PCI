from __future__ import annotations

import time
from tkinter import messagebox

from config import MIN_RADIUS_PX
from src.core.automatic_led_detector import (
    MAX_AUTOMATIC_LEDS,
    detect_lit_leds,
)
from src.models.led_selection import LedSelection


CAMERA_RADIUS_REFERENCE_DIMENSION = 1280


class AutomaticLedDetectionMixin:
    """Executa a detecção somente quando solicitada na parametrização."""

    def criar_callbacks(self) -> dict:
        callbacks = super().criar_callbacks()
        callbacks["detectar_leds_automaticamente"] = (
            self.detectar_leds_automaticamente
        )
        return callbacks

    def _obter_frame_deteccao_automatica(self):
        self._deteccao_automatica_usando_camera = False

        if self.camera_ativa:
            service = self.camera_service
            if service is None or self.camera_desconectada:
                return None

            snapshot = service.obter_snapshot(self.camera_ultimo_frame_id)
            self.camera_estado_anterior = snapshot.estado

            if snapshot.estado != service.ESTADO_CONECTADA:
                return None

            if snapshot.frame is not None:
                self.camera_ultimo_frame_id = snapshot.frame_id
                self.camera_frame_atual = snapshot.frame

            if self.camera_frame_atual is None:
                return None

            self._deteccao_automatica_usando_camera = True
            return self.camera_frame_atual.copy()

        if self.imagem_original is None:
            return None

        return self.imagem_original.copy()

    def _obter_raios_deteccao_automatica(self, frame) -> tuple[int, ...]:
        raio_configurado = max(MIN_RADIUS_PX, int(self.raio_atual_px))

        if not getattr(self, "_deteccao_automatica_usando_camera", False):
            return (raio_configurado,)

        altura, largura = frame.shape[:2]
        maior_dimensao = max(1, int(largura), int(altura))
        escala = min(
            1.0,
            maior_dimensao / float(CAMERA_RADIUS_REFERENCE_DIMENSION),
        )
        raio_escalado = max(
            MIN_RADIUS_PX,
            int(round(raio_configurado * escala)),
        )
        raio_intermediario = max(
            MIN_RADIUS_PX,
            int(round((raio_escalado + raio_configurado) / 2.0)),
        )

        raios = []
        for raio in (
            raio_escalado,
            raio_intermediario,
            raio_configurado,
        ):
            if raio not in raios:
                raios.append(raio)
        return tuple(raios)

    @staticmethod
    def _copiar_leds_detectados(leds) -> list[LedSelection]:
        return [
            LedSelection(
                id=led.id,
                centro_x=led.centro_x,
                centro_y=led.centro_y,
                raio=led.raio,
            )
            for led in leds
        ]

    def _detectar_em_multiplas_escalas(self, frame, camera_ao_vivo: bool):
        raios = self._obter_raios_deteccao_automatica(frame)
        perfil = "camera" if camera_ao_vivo else "strict"
        raio_configurado = max(MIN_RADIUS_PX, int(self.raio_atual_px))
        tentativas = []

        for raio in raios:
            resultado = detect_lit_leds(
                image=frame,
                radius=raio,
                max_leds=MAX_AUTOMATIC_LEDS,
                profile=perfil,
            )
            tentativas.append((resultado, raio))

        return max(
            tentativas,
            key=lambda item: (
                len(item[0].leds),
                item[0].candidate_count,
                -abs(item[1] - raio_configurado),
            ),
        )

    def detectar_leds_automaticamente(self) -> None:
        if getattr(self, "operacao_ativa", False):
            return

        camera_ao_vivo = bool(self.camera_ativa)
        pausa_camera_anterior = bool(self.camera_em_pausa_analise)

        if self.leds_selecionados:
            substituir = messagebox.askyesno(
                "Substituir seleção atual",
                (
                    "A detecção automática substituirá as máscaras que estão "
                    "atualmente na tela. Deseja continuar?"
                ),
                parent=self.root,
            )
            if not substituir:
                return

        if camera_ao_vivo:
            self.camera_em_pausa_analise = True

        try:
            frame = self._obter_frame_deteccao_automatica()
            if frame is None:
                messagebox.showwarning(
                    "Detecção automática",
                    (
                        "A câmera ainda não entregou um frame válido. "
                        "Aguarde a imagem ao vivo aparecer e tente novamente."
                        if camera_ao_vivo
                        else "Carregue uma imagem da placa antes de detectar LEDs."
                    ),
                    parent=self.root,
                )
                self.view.atualizar_status(
                    "Detecção automática aguardando um frame válido da câmera."
                    if camera_ao_vivo
                    else "Detecção automática sem imagem disponível."
                )
                return

            self.view.atualizar_status(
                "Analisando o frame ao vivo em múltiplas escalas..."
                if camera_ao_vivo
                else "Detectando LEDs acesos automaticamente..."
            )
            self.root.update_idletasks()

            inicio = time.perf_counter()
            resultado, raio_deteccao = self._detectar_em_multiplas_escalas(
                frame,
                camera_ao_vivo,
            )
            tempo_total = time.perf_counter() - inicio

            if not resultado.leds:
                messagebox.showwarning(
                    "Detecção automática",
                    (
                        "Nenhum LED aceso foi identificado com segurança.\n\n"
                        "Verifique foco, exposição, enquadramento e se os LEDs "
                        "estão realmente acesos."
                    ),
                    parent=self.root,
                )
                self.view.atualizar_status(
                    "Detecção automática concluída sem LEDs válidos."
                )
                return

            self.imagem_original = frame
            self.altura_original, self.largura_original = frame.shape[:2]
            self.leds_selecionados = self._copiar_leds_detectados(
                resultado.leds
            )
            self.resultados_led_atual = []

            if camera_ao_vivo:
                self.guias_leds_fixos_visiveis = False
                self.selecao_manual_camera_ativa = True
                self.modo_atual = "selecionar_leds_camera"
                self.view.selecao_manual_camera_visivel = True
                self.leds_manuais_camera = self._copiar_leds_detectados(
                    resultado.leds
                )
            else:
                self.modo_atual = "selecionar_leds_analise"

            if hasattr(self, "_limpar_estado_editor_led"):
                self._limpar_estado_editor_led()

            self.view.atualizar_estado_selecao_led(True)
            self.view.preparar_imagem_para_exibicao(self.imagem_original)

            if hasattr(self, "_redesenhar_editor_led"):
                self._redesenhar_editor_led(atualizar_auxiliares=True)
            else:
                self.view.desenhar_canvas(
                    self.leds_selecionados,
                    self.resultados_led_atual,
                )
                self.atualizar_renderizacoes_visuais(
                    self.leds_selecionados
                )
                self.atualizar_painel_inicial()

            limite_texto = (
                " O limite de 50 LEDs foi aplicado."
                if resultado.truncated
                else ""
            )
            origem_texto = " no frame ao vivo" if camera_ao_vivo else ""
            self.view.atualizar_status(
                f"Detecção automática{origem_texto}: "
                f"{len(self.leds_selecionados)} LEDs selecionados com raio "
                f"{raio_deteccao}px em {tempo_total:.3f} s."
                f"{limite_texto} Revise as máscaras antes de salvar o projeto."
            )
        finally:
            if camera_ao_vivo:
                self.camera_em_pausa_analise = pausa_camera_anterior
