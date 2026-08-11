from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from config import MAX_RADIUS_PX, MIN_RADIUS_PX
from src.core.classifier import ReferenceLedClassifier
from src.core.feature_extractor import extrair_features_selecao, validar_roi_selecao
from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.core.segment_low_light import aplicar_diagnostico_pouca_luz
from src.core.visual_renderer import criar_imagem_resultados_visuais
from src.infra.camera_service import CameraService
from src.models.led_selection import LedSelection
from src.platform.bulk_roi_editor import copiar_led
from src.platform.reference_debug_context import criar_contexto_debug_referencias


TEMPO_RETORNO_CAMERA_MS = 3000


def _copiar_lista(leds):
    return [copiar_led(led) for led in (leds or ())]


def _tem_segmentos(leds) -> bool:
    return any(
        normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO
        for led in (leds or ())
    )


def _referencia_pouca_luz_ativa(app) -> bool:
    """Só habilita POUCA_LUZ quando há amostra ativa no contexto atual."""
    grupos = getattr(app, "_referencias_ativas_por_tipo", None)
    if isinstance(grupos, dict):
        return bool(grupos.get("pouca_luz"))
    return getattr(app, "features_referencia_pouca_luz", None) is not None


class SegmentDisplayRuntimeMixin:
    """Mantém a geometria mista nos fluxos legados do ODIN."""

    def _restaurar_manuais_segmento_na_visualizacao(
        self,
        manuais,
        redesenhar: bool = True,
    ) -> bool:
        """Impede que o fluxo legado converta segmentos manuais em círculos."""
        itens = _copiar_lista(manuais)
        if not itens or not _tem_segmentos(itens):
            return False
        if bool(getattr(self, "guias_leds_fixos_visiveis", False)):
            return False

        self.leds_manuais_camera = _copiar_lista(itens)
        self.leds_selecionados = _copiar_lista(itens)
        self.view.selecao_manual_camera_visivel = True

        if (
            redesenhar
            and not bool(getattr(self, "camera_em_pausa_analise", False))
            and getattr(self, "imagem_original", None) is not None
        ):
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
        return True

    def iniciar_selecao_led(self) -> None:
        manuais_antes = _copiar_lista(getattr(self, "leds_manuais_camera", ()))
        super().iniciar_selecao_led()
        self._restaurar_manuais_segmento_na_visualizacao(
            manuais_antes,
            redesenhar=True,
        )

    def atualizar_frame_camera(self) -> None:
        manuais_antes = _copiar_lista(getattr(self, "leds_manuais_camera", ()))
        super().atualizar_frame_camera()
        self._restaurar_manuais_segmento_na_visualizacao(
            manuais_antes,
            redesenhar=True,
        )

    def retomar_tela_ao_vivo_apos_analise(self) -> None:
        manuais_antes = _copiar_lista(getattr(self, "leds_manuais_camera", ()))
        super().retomar_tela_ao_vivo_apos_analise()
        self._restaurar_manuais_segmento_na_visualizacao(
            manuais_antes,
            redesenhar=True,
        )

    def salvar_leds_fixos(self) -> None:
        if not self.leds_selecionados:
            messagebox.showwarning(
                "Atenção",
                "Nenhuma ROI foi selecionada para salvar como posição fixa.",
            )
            return

        self.leds_fixos_configurados = _copiar_lista(self.leds_selecionados)
        self.configuracao_atual = self.config_repository.salvar_leds_fixos(
            self.leds_fixos_configurados,
            largura_base=None,
            altura_base=None,
        )

        self.modo_atual = "ocioso"
        self.view.atualizar_estado_selecao_led(False)
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self.atualizar_renderizacoes_visuais(self.leds_selecionados)
        self.view.atualizar_status(
            f"{len(self.leds_fixos_configurados)} ROIs fixas salvas."
        )
        self.atualizar_painel_inicial()

        capturar_guard = getattr(self, "_mask_guard_capture", None)
        aplicar_guard = getattr(self, "_mask_guard_enforce", None)
        if callable(capturar_guard):
            capturar_guard(force=True, source=self.leds_fixos_configurados)
        if callable(aplicar_guard):
            aplicar_guard()

        messagebox.showinfo(
            "ODIN",
            f"{len(self.leds_fixos_configurados)} ROIs fixas salvas com sucesso.",
        )

    def capturar_frame_camera_para_analise(self, evento=None) -> None:
        del evento
        if not self.camera_ativa or self.camera_em_pausa_analise:
            return
        if (
            self.camera_service is None
            or self.camera_desconectada
            or self.camera_estado_anterior != CameraService.ESTADO_CONECTADA
        ):
            self.view.atualizar_status(
                "Câmera desconectada. Aguarde a reconexão automática."
            )
            return
        if self.camera_frame_atual is None:
            self.view.atualizar_status("Aguarde a câmera terminar de estabilizar.")
            return

        self.camera_em_pausa_analise = True
        self.imagem_original = self.camera_frame_atual.copy()
        self.caminho_imagem_atual = "camera_usb"
        self.altura_original, self.largura_original = self.imagem_original.shape[:2]

        if self.leds_manuais_camera and not self.guias_leds_fixos_visiveis:
            leds_validos = [
                copiar_led(led)
                for led in self.leds_manuais_camera
                if validar_roi_selecao(
                    led,
                    self.largura_original,
                    self.altura_original,
                )
            ]
        elif self.guias_leds_fixos_visiveis:
            self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()
            leds_validos = self.adaptar_leds_fixos_para_frame_camera(
                self.leds_fixos_configurados
            )
        else:
            leds_validos = []

        if not leds_validos:
            self.camera_em_pausa_analise = False
            self.view.atualizar_status(
                "Nenhuma ROI selecionada. Use Carregar LEDs ou Selecionar LEDs."
            )
            return

        self.leds_selecionados = _copiar_lista(leds_validos)
        self.resultados_led_atual = []
        self.view.preparar_imagem_para_exibicao(self.imagem_original)
        self.view.desenhar_canvas(self.leds_selecionados, self.resultados_led_atual)
        self.view.atualizar_status("Frame capturado. Executando análise...")

        self.analisar_led_selecionado()

        if not self.camera_ativa:
            return
        if self.camera_desconectada:
            self.camera_em_pausa_analise = False
            self.view.atualizar_faixa_resultado()
            self.view.atualizar_status(
                "Câmera desconectada. Reconectando automaticamente..."
            )
            return

        self.view.atualizar_status(
            "Análise concluída. Retornando à câmera em 3 segundos..."
        )
        if self.camera_retomada_after_id is not None:
            try:
                self.root.after_cancel(self.camera_retomada_after_id)
            except Exception:
                pass
        self.camera_retomada_after_id = self.root.after(
            TEMPO_RETORNO_CAMERA_MS,
            self.retomar_tela_ao_vivo_apos_analise,
        )

    def analisar_led_selecionado(self) -> None:
        if self.camera_ativa and not self.camera_em_pausa_analise:
            self.capturar_frame_camera_para_analise()
            return
        if self.imagem_original is None:
            messagebox.showwarning("Atenção", "Carregue uma imagem antes de analisar.")
            return
        if not self.leds_selecionados:
            messagebox.showwarning("Atenção", "Selecione uma ou mais ROIs antes de analisar.")
            return

        self.carregar_referencias_automaticamente_se_necessario()
        if not self.referencias_disponiveis():
            messagebox.showwarning(
                "Atenção",
                "Carregue ou salve as duas referências fixas antes de analisar.",
            )
            return

        diagnostico_pouca_luz_habilitado = _referencia_pouca_luz_ativa(self)
        classificador = ReferenceLedClassifier(
            features_referencia_acesa=self.features_referencia_acesa,
            features_referencia_apagada=self.features_referencia_apagada,
        )
        resultados_led = []
        for led in self.leds_selecionados:
            features_atual = extrair_features_selecao(self.imagem_original, led)
            resultado = classificador.classificar_led_por_referencia(
                features_atual=features_atual,
                centro_x=led.centro_x,
                centro_y=led.centro_y,
                raio=led.raio,
            )
            resultado.id = led.id
            resultado.tipo_roi = led.tipo_roi
            resultado.largura = led.largura
            resultado.altura = led.altura
            resultado.angulo = led.angulo
            aplicar_diagnostico_pouca_luz(
                resultado,
                led.tipo_roi,
                habilitado=diagnostico_pouca_luz_habilitado,
            )
            resultados_led.append(resultado)

        self.resultados_led_atual = resultados_led
        self.modo_atual = "ocioso"
        self.view.atualizar_estado_selecao_led(False)
        output_paths = self.result_repository.salvar_resultado_analise_multiplos(
            imagem_original=self.imagem_original,
            resultados_led=resultados_led,
            caminho_imagem_atual=self.caminho_imagem_atual,
            caminho_referencia_acesa=self.caminho_referencia_acesa,
            caminho_referencia_apagada=self.caminho_referencia_apagada,
            features_referencia_acesa=self.features_referencia_acesa,
            features_referencia_apagada=self.features_referencia_apagada,
            leds_selecionados=self.leds_selecionados,
            salvar_resultados_analise=self.salvar_resultados_analise,
        )

        imagem_resultado = criar_imagem_resultados_visuais(
            self.imagem_original,
            resultados_led,
        )
        self.view.preparar_imagem_para_exibicao(imagem_resultado)
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self.atualizar_renderizacoes_visuais(resultados_led)

        from src.core.debug_formatter import formatar_resultado_textual_multiplos

        contexto_referencias = criar_contexto_debug_referencias(self)
        self.view.escrever_resultados(
            formatar_resultado_textual_multiplos(
                resultados_led,
                output_paths,
                contexto_referencias=contexto_referencias,
            )
        )
        self.view.atualizar_faixa_resultado_multiplos(resultados_led)
        self.view.atualizar_status("Análise concluída.")

    def _ajustar_raio_apenas_circulos(self, incremento: int) -> None:
        self.raio_atual_px = min(
            MAX_RADIUS_PX,
            max(MIN_RADIUS_PX, int(self.raio_atual_px) + int(incremento)),
        )
        self.view.atualizar_label_raio(self.raio_atual_px)

        listas = []
        if self.camera_ativa and self.leds_manuais_camera:
            listas.append(self.leds_manuais_camera)
        listas.append(self.leds_selecionados)
        vistos = set()
        for lista in listas:
            for led in lista:
                if id(led) in vistos:
                    continue
                vistos.add(id(led))
                if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) != TIPO_ROI_SEGMENTO:
                    led.raio = self.raio_atual_px

        if self.camera_ativa and self.leds_manuais_camera:
            self.leds_selecionados = _copiar_lista(self.leds_manuais_camera)

        if self.leds_selecionados and self.imagem_original is not None:
            self.resultados_led_atual = []
            self.view.preparar_imagem_para_exibicao(self.imagem_original)
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            if self.camera_ativa:
                self.atualizar_renderizacoes_camera_se_necessario(forcar=True)
            else:
                self.atualizar_renderizacoes_visuais(self.leds_selecionados)
            self.view.atualizar_faixa_resultado()
        self.view.atualizar_status(
            f"Raio dos círculos ajustado para {self.raio_atual_px}px. Segmentos não foram alterados."
        )
        self.atualizar_painel_inicial()

    def aumentar_raio(self) -> None:
        self._ajustar_raio_apenas_circulos(1)

    def diminuir_raio(self) -> None:
        self._ajustar_raio_apenas_circulos(-1)
