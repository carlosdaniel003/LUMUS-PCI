from __future__ import annotations

import inspect
import unittest

import numpy as np

from src.core.roi_geometry import pontos_segmento
from src.models.led_selection import LedSelection
from src.platform.display_mask_editor import DisplayMaskEditorWindow
from src.platform.display_mask_geometry import (
    TOOL_MASS,
    criar_poligono_display_por_pontos,
    pontos_mascara_display,
)
from src.platform.freeform_segment_roi import criar_segmento_livre_por_pontos
from src.platform.segment_project_geometry_persistence import (
    SegmentProjectGeometryPersistenceMixin,
    restaurar_tipo_roi_apos_adaptacao,
)


class _ViewFake:
    def __init__(self) -> None:
        self.selecao_manual_camera_visivel = False
        self.ultimo_desenho = []

    def desenhar_canvas(self, leds, _resultados) -> None:
        self.ultimo_desenho = list(leds or ())


class _RuntimeLegadoBase:
    def atualizar_frame_camera(self) -> None:
        origem = self.leds_manuais_camera[0]
        # Simula exatamente o caminho legado que perdia tipo_roi e vértices.
        self.leds_selecionados = [
            LedSelection(
                id=origem.id,
                centro_x=origem.centro_x,
                centro_y=origem.centro_y,
                raio=origem.raio,
            )
        ]

    def analisar_led_selecionado(self):
        self.geometria_recebida_na_analise = list(self.leds_selecionados)
        return self.geometria_recebida_na_analise


class _RuntimeHarness(
    SegmentProjectGeometryPersistenceMixin,
    _RuntimeLegadoBase,
):
    pass


class RoiGeometryF2F3ConsistencyTests(unittest.TestCase):
    def _segmento_livre(self):
        return criar_segmento_livre_por_pontos(
            [(30, 30), (92, 24), (108, 48), (72, 62), (34, 54)],
            "LED_001",
        )

    def test_f3_reproduz_exatamente_o_contorno_ponto_a_ponto_do_f2(self):
        led = self._segmento_livre()
        pontos_f2 = pontos_segmento(led)
        mask = criar_poligono_display_por_pontos(
            pontos_f2,
            id_mascara="MASK_001",
        )
        pontos_f3 = np.asarray(pontos_mascara_display(mask), dtype=np.float32)
        esperado = np.rint(np.asarray(pontos_f2, dtype=np.float32))

        self.assertEqual("polygon", mask["type"])
        self.assertEqual(len(esperado), len(pontos_f3))
        np.testing.assert_allclose(pontos_f3, esperado, atol=1e-5)

    def test_fallback_circular_restaura_segmento_livre_e_vertices(self):
        original = self._segmento_livre()
        legado = LedSelection(
            id=original.id,
            centro_x=original.centro_x + 10,
            centro_y=original.centro_y + 20,
            raio=original.raio * 2,
        )

        restaurado = restaurar_tipo_roi_apos_adaptacao(original, legado)

        self.assertTrue(restaurado.eh_segmento)
        self.assertTrue(restaurado.eh_segmento_livre)
        self.assertEqual(legado.centro_x, restaurado.centro_x)
        self.assertEqual(legado.centro_y, restaurado.centro_y)
        np.testing.assert_allclose(
            np.asarray(restaurado.pontos_segmento_livre),
            np.asarray(original.pontos_segmento_livre) * 2.0,
            atol=1e-5,
        )

    def test_refresh_camera_nao_transforma_ponto_a_ponto_em_circulo(self):
        app = object.__new__(_RuntimeHarness)
        original = self._segmento_livre()
        app.camera_ativa = True
        app.camera_em_pausa_analise = False
        app.leds_manuais_camera = [original]
        app.leds_selecionados = []
        app.resultados_led_atual = []
        app.view = _ViewFake()

        app.atualizar_frame_camera()

        self.assertEqual(1, len(app.leds_selecionados))
        atual = app.leds_selecionados[0]
        self.assertTrue(atual.eh_segmento_livre)
        self.assertEqual(
            list(original.pontos_segmento_livre),
            list(atual.pontos_segmento_livre),
        )
        self.assertTrue(app.view.ultimo_desenho[0].eh_segmento_livre)

    def test_analise_recebe_poligono_real_mesmo_se_estado_visual_foi_reduzido(self):
        app = object.__new__(_RuntimeHarness)
        original = self._segmento_livre()
        app.camera_ativa = True
        app.camera_em_pausa_analise = False
        app.leds_manuais_camera = [original]
        app.leds_selecionados = [
            LedSelection(
                id=original.id,
                centro_x=original.centro_x,
                centro_y=original.centro_y,
                raio=original.raio,
            )
        ]
        app.resultados_led_atual = []
        app.view = _ViewFake()

        app.analisar_led_selecionado()

        recebido = app.geometria_recebida_na_analise[0]
        self.assertTrue(recebido.eh_segmento_livre)
        self.assertEqual(
            list(original.pontos_segmento_livre),
            list(recebido.pontos_segmento_livre),
        )

    def test_toolbar_f3_mantem_selecao_em_massa_em_linha_propria_visivel(self):
        source = inspect.getsource(DisplayMaskEditorWindow._toolbar)
        self.assertIn("TOOL_MASS", source)
        self.assertIn("Seleção em massa", source)
        self.assertIn("grid_columnconfigure", source)
        self.assertNotIn("height=72", source.replace(" ", ""))
        self.assertEqual("mass", TOOL_MASS)


if __name__ == "__main__":
    unittest.main()
