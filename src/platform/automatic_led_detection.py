from __future__ import annotations

from tkinter import messagebox

from src.core.automatic_led_detector import (
    MAX_AUTOMATIC_LEDS,
    detect_lit_leds,
)
from src.models.led_selection import LedSelection


class AutomaticLedDetectionMixin:
    """Executa a detecção somente quando solicitada na parametrização."""

    def criar_callbacks(self) -> dict:
        callbacks = super().criar_callbacks()
        callbacks["detectar_leds_automaticamente"] = (
            self.detectar_leds_automaticamente
        )
        return callbacks

    def _obter_frame_deteccao_automatica(self):
        if self.camera_ativa:
            if self.camera_desconectada or self.camera_frame_atual is None:
                return None
            return self.camera_frame_atual.copy()

        if self.imagem_original is None:
            return None
        return self.imagem_original.copy()

    def detectar_leds_automaticamente(self) -> None:
        if getattr(self, "operacao_ativa", False):
            return

        frame = self._obter_frame_deteccao_automatica()
        if frame is None:
            messagebox.showwarning(
                "Detecção automática",
                "Aguarde a câmera conectar ou carregue uma imagem da placa.",
                parent=self.root,
            )
            return

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

        self.view.atualizar_status(
            "Detectando LEDs acesos automaticamente..."
        )
        self.root.update_idletasks()

        resultado = detect_lit_leds(
            image=frame,
            radius=self.raio_atual_px,
            max_leds=MAX_AUTOMATIC_LEDS,
        )

        if not resultado.leds:
            messagebox.showwarning(
                "Detecção automática",
                (
                    "Nenhum LED aceso foi identificado com segurança.\n\n"
                    "Verifique foco, exposição, brilho da placa e se os LEDs "
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
        self.leds_selecionados = [
            LedSelection(
                id=led.id,
                centro_x=led.centro_x,
                centro_y=led.centro_y,
                raio=led.raio,
            )
            for led in resultado.leds
        ]
        self.resultados_led_atual = []

        if self.camera_ativa:
            self.guias_leds_fixos_visiveis = False
            self.selecao_manual_camera_ativa = True
            self.modo_atual = "selecionar_leds_camera"
            self.view.selecao_manual_camera_visivel = True
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
        self.view.atualizar_status(
            f"Detecção automática: {len(self.leds_selecionados)} LEDs "
            f"selecionados em {resultado.elapsed_seconds:.3f} s."
            f"{limite_texto} Revise as máscaras antes de salvar o projeto."
        )
