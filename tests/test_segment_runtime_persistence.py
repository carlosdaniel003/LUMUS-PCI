import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from src.core.roi_geometry import TIPO_ROI_SEGMENTO
from src.models.led_features import LedFeatures
from src.models.led_selection import LedSelection
from src.platform.segment_display_runtime import SegmentDisplayRuntimeMixin


class FakeView:
    def __init__(self):
        self.selecao_manual_camera_visivel = False
        self.desenhos = []
        self.status = ""

    def desenhar_canvas(self, leds, resultados):
        self.desenhos.append((list(leds), list(resultados)))

    def atualizar_estado_selecao_led(self, _ativo):
        return None

    def preparar_imagem_para_exibicao(self, _imagem):
        return None

    def escrever_resultados(self, _texto):
        return None

    def atualizar_faixa_resultado_multiplos(self, _resultados):
        return None

    def atualizar_status(self, texto):
        self.status = texto


class FakeResultRepository:
    def salvar_resultado_analise_multiplos(self, **_kwargs):
        return {}


class BaseRuntimeFake:
    def __init__(self):
        self.view = FakeView()
        self.camera_ativa = True
        self.camera_em_pausa_analise = False
        self.guias_leds_fixos_visiveis = False
        self.selecao_manual_camera_ativa = False
        self.imagem_original = np.zeros((120, 220, 3), dtype=np.uint8)
        self.leds_manuais_camera = [
            LedSelection(
                "SEG_001",
                100,
                60,
                1,
                tipo_roi="segmento",
                largura=80,
                altura=16,
                angulo=7.5,
            )
        ]
        self.leds_selecionados = list(self.leds_manuais_camera)
        self.resultados_led_atual = []
        self.features_referencia_acesa = LedFeatures(v_mean=220)
        self.features_referencia_apagada = LedFeatures(v_mean=20)
        self.result_repository = FakeResultRepository()
        self.caminho_imagem_atual = "camera_usb"
        self.caminho_referencia_acesa = None
        self.caminho_referencia_apagada = None
        self.salvar_resultados_analise = False
        self.modo_atual = "tela_ao_vivo"

    def atualizar_frame_camera(self):
        # Reproduz o bug legado: a geometria do segmento era descartada e o
        # raio de compatibilidade passava a ser desenhado como uma bolinha.
        self.leds_selecionados = [
            LedSelection(
                led.id,
                led.centro_x,
                led.centro_y,
                led.raio,
            )
            for led in self.leds_manuais_camera
        ]
        self.view.desenhar_canvas(self.leds_selecionados, [])

    def iniciar_selecao_led(self):
        self.selecao_manual_camera_ativa = not self.selecao_manual_camera_ativa
        self.modo_atual = (
            "selecionar_leds_camera"
            if self.selecao_manual_camera_ativa
            else "tela_ao_vivo"
        )
        self.leds_selecionados = [
            LedSelection(led.id, led.centro_x, led.centro_y, led.raio)
            for led in self.leds_manuais_camera
        ]

    def retomar_tela_ao_vivo_apos_analise(self):
        self.camera_em_pausa_analise = False
        self.modo_atual = "tela_ao_vivo"
        self.leds_selecionados = [
            LedSelection(led.id, led.centro_x, led.centro_y, led.raio)
            for led in self.leds_manuais_camera
        ]

    def carregar_referencias_automaticamente_se_necessario(self):
        return None

    def referencias_disponiveis(self):
        return True

    def atualizar_renderizacoes_visuais(self, _alvo=None):
        return None

    def atualizar_painel_inicial(self):
        return None


class RuntimeFake(SegmentDisplayRuntimeMixin, BaseRuntimeFake):
    pass


class FakeClassifier:
    def __init__(self, **_kwargs):
        pass

    def classificar_led_por_referencia(
        self,
        features_atual,
        centro_x,
        centro_y,
        raio,
    ):
        return SimpleNamespace(
            id="",
            status="ACESO",
            valor_binario=1,
            centro_x=centro_x,
            centro_y=centro_y,
            raio=raio,
            features=features_atual,
            tipo_roi="circulo",
            largura=None,
            altura=None,
            angulo=0.0,
        )


class SegmentRuntimePersistenceTests(unittest.TestCase):
    def _assert_segmento_preservado(self, app):
        self.assertEqual(1, len(app.leds_selecionados))
        led = app.leds_selecionados[0]
        self.assertEqual(TIPO_ROI_SEGMENTO, led.tipo_roi)
        self.assertEqual(80, led.largura)
        self.assertEqual(16, led.altura)
        self.assertAlmostEqual(7.5, led.angulo)

    def test_live_nao_converte_segmento_em_bolinha_apos_fechar_editor(self):
        app = RuntimeFake()
        app.selecao_manual_camera_ativa = False
        app.atualizar_frame_camera()
        self._assert_segmento_preservado(app)
        self.assertTrue(app.view.selecao_manual_camera_visivel)

    def test_toggle_do_editor_preserva_forma_segmento(self):
        app = RuntimeFake()
        app.selecao_manual_camera_ativa = True
        app.iniciar_selecao_led()
        self.assertFalse(app.selecao_manual_camera_ativa)
        self._assert_segmento_preservado(app)

    def test_retorno_da_analise_preserva_forma_segmento(self):
        app = RuntimeFake()
        app.camera_em_pausa_analise = True
        app.retomar_tela_ao_vivo_apos_analise()
        self._assert_segmento_preservado(app)

    def test_analise_recebe_roi_segmento_e_resultado_mantem_geometria(self):
        app = RuntimeFake()
        app.camera_ativa = False
        app.camera_em_pausa_analise = False
        segmento = app.leds_selecionados[0]
        features = LedFeatures(v_mean=200, area_pixels=900)

        with (
            patch(
                "src.platform.segment_display_runtime.extrair_features_selecao",
                return_value=features,
            ) as extrair,
            patch(
                "src.platform.segment_display_runtime.ReferenceLedClassifier",
                FakeClassifier,
            ),
            patch(
                "src.platform.segment_display_runtime.criar_imagem_resultados_visuais",
                side_effect=lambda imagem, _resultados: imagem,
            ),
            patch(
                "src.core.debug_formatter.formatar_resultado_textual_multiplos",
                return_value="ok",
            ),
        ):
            app.analisar_led_selecionado()

        extrair.assert_called_once()
        self.assertIs(extrair.call_args.args[1], segmento)
        self.assertEqual(1, len(app.resultados_led_atual))
        resultado = app.resultados_led_atual[0]
        self.assertEqual(TIPO_ROI_SEGMENTO, resultado.tipo_roi)
        self.assertEqual(80, resultado.largura)
        self.assertEqual(16, resultado.altura)
        self.assertAlmostEqual(7.5, resultado.angulo)


if __name__ == "__main__":
    unittest.main()
