from __future__ import annotations

from tkinter import messagebox

from config import MIN_RADIUS_PX
from src.core.automatic_led_detector import (
    MAX_AUTOMATIC_LEDS,
    detect_lit_leds,
)
from src.models.led_selection import LedSelection


# O raio padrão de 15 px foi definido usando imagens próximas de 1280 px de
# largura. No perfil Raspberry a câmera trabalha em 640x480 para preservar
# desempenho; portanto, a detecção precisa adaptar o raio à resolução real.
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

            # Solicita um frame novo diretamente ao serviço em vez de depender
            # apenas do último frame desenhado pela pré-visualização, que no
            # Raspberry é propositalmente atualizada em frequência reduzida.
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

    def _obter_raio_deteccao_automatica(self, frame) -> int:
        raio_configurado = max(MIN_RADIUS_PX, int(self.raio_atual_px))

        if not getattr(self, "_deteccao_automatica_usando_camera", False):
            return raio_configurado

        altura, largura = frame.shape[:2]
        maior_dimensao = max(1, int(largura), int(altura))
        escala = min(
            1.0,
            maior_dimensao / float(CAMERA_RADIUS_REFERENCE_DIMENSION),
        )

        return max(
            MIN_RADIUS_PX,
            int(round(raio_configurado * escala)),
        )

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
            # Impede que o loop de pré-visualização substitua a imagem e as
            # máscaras enquanto o frame atual está sendo processado.
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
                "Capturando frame e detectando LEDs acesos..."
                if camera_ao_vivo
                else "Detectando LEDs acesos automaticamente..."
            )
            self.root.update_idletasks()

            raio_deteccao = self._obter_raio_deteccao_automatica(frame)
            resultado = detect_lit_leds(
                image=frame,
                radius=raio_deteccao,
                max_leds=MAX_AUTOMATIC_LEDS,
            )

            # A escala automática atende ao perfil 640x480. Caso uma câmera
            # negocie outra área útil ou enquadramento, mantém-se uma tentativa
            # de compatibilidade com o raio configurado, somente se a primeira
            # passagem não encontrar nenhum LED.
            raio_configurado = max(MIN_RADIUS_PX, int(self.raio_atual_px))
            if (
                camera_ao_vivo
                and not resultado.leds
                and raio_deteccao != raio_configurado
            ):
                resultado = detect_lit_leds(
                    image=frame,
                    radius=raio_configurado,
                    max_leds=MAX_AUTOMATIC_LEDS,
                )
                raio_deteccao = raio_configurado

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

                # O loop da câmera reconstrói leds_selecionados a partir desta
                # lista a cada frame. Sem esta cópia, as máscaras detectadas
                # desapareciam imediatamente na pré-visualização ao vivo.
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
                f"{raio_deteccao}px em {resultado.elapsed_seconds:.3f} s."
                f"{limite_texto} Revise as máscaras antes de salvar o projeto."
            )
        finally:
            if camera_ao_vivo:
                self.camera_em_pausa_analise = pausa_camera_anterior
