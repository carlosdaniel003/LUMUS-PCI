import unittest

import numpy as np

from src.models.led_selection import LedSelection
from src.platform.led_mask_resolution_sync import (
    ResolutionSynchronizedLedMasksMixin,
    adapt_led_masks_to_resolution,
)


class FakeEngine:
    def __init__(self, width=1920, height=1080):
        self._frame_width = width
        self._frame_height = height
        self.invalidated = False

    def invalidate(self):
        self.invalidated = True
        self._frame_width = 0
        self._frame_height = 0


class FakeWindow:
    def __init__(self):
        self.preview = None

    def update_preview(self, frame, leds):
        self.preview = (frame.shape[:2], list(leds))


class FakeRoot:
    def after_cancel(self, _after_id):
        return None


class FakeView:
    def __init__(self):
        self.drawn = None

    def desenhar_canvas(self, leds, results):
        self.drawn = (list(leds), list(results))


class FakeRepository:
    def __init__(self):
        self.saved = []

    def obter_projeto_led_ativo(self):
        return "PLACA A"

    def salvar_leds_fixos(self, leds, projeto=None):
        self.saved.append((projeto, list(leds)))
        return {}

    def carregar_leds_fixos(self):
        return []


class DummyBase:
    def __init__(self):
        self.camera_frame_atual = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.imagem_original = self.camera_frame_atual
        self.largura_original = 1920
        self.altura_original = 1080
        self.leds_fixos_configurados = [
            LedSelection(
                id="LED_001",
                centro_x=960,
                centro_y=540,
                raio=30,
            ).com_normalizacao(1920, 1080)
        ]
        self.leds_manuais_camera = []
        self.leds_selecionados = []
        self.resultados_led_atual = []
        self.guias_leds_fixos_visiveis = True
        self.selecao_manual_camera_ativa = False
        self.operacao_ativa = True
        self.operacao_processando = False
        self.operacao_engine = FakeEngine()
        self.operacao_window = FakeWindow()
        self._operacao_preparo_after_id = None
        self.scheduled = []
        self.root = FakeRoot()
        self.view = FakeView()
        self.config_repository = FakeRepository()

    def _agendar_preparo_operacao(self, delay):
        self.scheduled.append(delay)

    def atualizar_frame_camera(self):
        return None

    def preparar_tela_operacao(self):
        return None

    def disparar_inspecao_operacao(self):
        return None

    def selecionar_led_para_analise(self, _x, _y):
        return None


class DummyApp(ResolutionSynchronizedLedMasksMixin, DummyBase):
    pass


class LedMaskResolutionSyncTests(unittest.TestCase):
    def test_mascara_acompanha_1080p_para_720p_e_volta(self):
        original = LedSelection(
            id="LED_001",
            centro_x=960,
            centro_y=540,
            raio=30,
        ).com_normalizacao(1920, 1080)

        hd = adapt_led_masks_to_resolution(
            [original],
            target_width=1280,
            target_height=720,
        ).adapted_leds[0]
        self.assertEqual((640, 360, 20), (hd.centro_x, hd.centro_y, hd.raio))

        full_hd = adapt_led_masks_to_resolution(
            [hd],
            target_width=1920,
            target_height=1080,
        ).adapted_leds[0]
        self.assertEqual(
            (960, 540, 30),
            (full_hd.centro_x, full_hd.centro_y, full_hd.raio),
        )

    def test_640x480_para_1920x1080_preserva_percentual_do_centro(self):
        original = LedSelection(
            id="LED_025",
            centro_x=160,
            centro_y=360,
            raio=20,
        ).com_normalizacao(640, 480)

        full_hd = adapt_led_masks_to_resolution(
            [original],
            target_width=1920,
            target_height=1080,
        ).adapted_leds[0]

        self.assertEqual((480, 810), (full_hd.centro_x, full_hd.centro_y))
        self.assertAlmostEqual(0.25, full_hd.centro_x / 1920.0, places=6)
        self.assertAlmostEqual(0.75, full_hd.centro_y / 1080.0, places=6)

    def test_raio_salvo_nao_e_truncado_pelo_limite_do_editor(self):
        original = LedSelection(
            id="LED_GRANDE",
            centro_x=320,
            centro_y=240,
            raio=20,
        ).com_normalizacao(640, 480)

        full_hd = adapt_led_masks_to_resolution(
            [original],
            target_width=1920,
            target_height=1080,
        ).adapted_leds[0]

        # O editor limita a criação manual, mas uma máscara existente precisa
        # escalar 3x para continuar cobrindo a mesma região relativa.
        self.assertEqual(60, full_hd.raio)

    def test_roi_na_borda_nao_desaparece_ao_mudar_proporcao(self):
        original = LedSelection(
            id="LED_BORDA",
            centro_x=320,
            centro_y=20,
            raio=20,
        ).com_normalizacao(640, 480)

        adaptacao = adapt_led_masks_to_resolution(
            [original],
            target_width=1920,
            target_height=1080,
        )

        self.assertEqual(1, len(adaptacao.canonical_leds))
        self.assertEqual(1, len(adaptacao.adapted_leds))
        adaptado = adaptacao.adapted_leds[0]
        self.assertEqual((960, 45, 60), (
            adaptado.centro_x,
            adaptado.centro_y,
            adaptado.raio,
        ))
        self.assertTrue(adaptado.possui_coordenadas_normalizadas())

    def test_ciclo_repetido_640_1920_usa_base_canonica_sem_deriva(self):
        atual = LedSelection(
            id="LED_CICLO",
            centro_x=211,
            centro_y=137,
            raio=17,
        ).com_normalizacao(640, 480)
        esperado = (211, 137, 17)

        for _ in range(100):
            atual = adapt_led_masks_to_resolution(
                [atual],
                target_width=1920,
                target_height=1080,
            ).adapted_leds[0]
            atual = adapt_led_masks_to_resolution(
                [atual],
                target_width=640,
                target_height=480,
            ).adapted_leds[0]

        self.assertEqual(esperado, (atual.centro_x, atual.centro_y, atual.raio))
        self.assertTrue(atual.possui_coordenadas_normalizadas())

    def test_segmento_livre_escala_vertices_sem_deslocar_centro(self):
        segmento = LedSelection(
            id="SEG_LIVRE",
            centro_x=320,
            centro_y=240,
            raio=1,
            tipo_roi="segmento",
            pontos_segmento_livre=[
                (-30.0, -10.0),
                (20.0, -10.0),
                (35.0, 15.0),
                (-25.0, 20.0),
            ],
        ).com_normalizacao(640, 480)

        adaptado = adapt_led_masks_to_resolution(
            [segmento],
            target_width=1920,
            target_height=1080,
        ).adapted_leds[0]

        self.assertEqual((960, 540), (adaptado.centro_x, adaptado.centro_y))
        self.assertEqual(
            [(-90.0, -22.5), (60.0, -22.5), (105.0, 33.75), (-75.0, 45.0)],
            adaptado.pontos_segmento_livre,
        )

    def test_led_legado_e_escalado_mesmo_quando_caberia_sem_escala(self):
        legacy = LedSelection(
            id="LED_001",
            centro_x=960,
            centro_y=540,
            raio=30,
        )
        adaptation = adapt_led_masks_to_resolution(
            [legacy],
            target_width=1280,
            target_height=720,
            reference_width=1920,
            reference_height=1080,
        )
        adapted = adaptation.adapted_leds[0]

        self.assertTrue(adaptation.migrated_legacy)
        self.assertEqual((640, 360, 20), (
            adapted.centro_x,
            adapted.centro_y,
            adapted.raio,
        ))
        self.assertTrue(
            adaptation.canonical_leds[0].possui_coordenadas_normalizadas()
        )

    def test_troca_de_resolucao_atualiza_preview_e_motor_f2(self):
        app = DummyApp()
        app._mask_resolution_active = (1920, 1080)

        app._synchronize_masks_with_current_frame()

        preview_led = app.operacao_leds_preview[0]
        self.assertEqual((640, 360, 20), (
            preview_led.centro_x,
            preview_led.centro_y,
            preview_led.raio,
        ))
        self.assertTrue(app.operacao_engine.invalidated)
        self.assertEqual([20], app.scheduled)
        self.assertEqual((720, 1280), app.operacao_window.preview[0])

    def test_preparo_forcado_nao_cria_loop_de_reagendamento(self):
        app = DummyApp()
        app._mask_resolution_active = (1280, 720)

        app._synchronize_masks_with_current_frame(
            force=True,
            schedule_operation_prepare=False,
        )

        self.assertEqual([], app.scheduled)

    def test_mascara_legada_e_persistida_normalizada_por_projeto(self):
        app = DummyApp()
        app.leds_fixos_configurados = [
            LedSelection(
                id="LED_LEGADO",
                centro_x=640,
                centro_y=360,
                raio=20,
            )
        ]
        app._mask_resolution_active = (1280, 720)

        app._synchronize_masks_with_current_frame(force=True)

        self.assertEqual(1, len(app.config_repository.saved))
        project, saved = app.config_repository.saved[0]
        self.assertEqual("PLACA A", project)
        self.assertTrue(saved[0].possui_coordenadas_normalizadas())


if __name__ == "__main__":
    unittest.main()
