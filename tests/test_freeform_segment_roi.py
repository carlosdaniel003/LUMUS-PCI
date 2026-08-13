import inspect
import unittest

import numpy as np

import src.platform.bulk_roi_editor as bulk_roi_editor
from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    criar_mascara_roi_global,
    ponto_dentro_roi,
    pontos_segmento,
)
from src.models.led_selection import LedSelection
from src.platform.freeform_segment_persistence import (
    assinatura_geometria_segmento_livre,
    copiar_mascara_absoluta_segmento_livre,
)
from src.platform.freeform_segment_roi import (
    FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX,
    FreeformSegmentDrawingMixin,
    criar_segmento_livre_por_pontos,
)
from src.platform.fullscreen_led_selection import FullscreenLedSelectionMixin
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp
from src.platform.segment_display_roi_editor import criar_segmento_por_arrasto


class FreeformSegmentRoiTests(unittest.TestCase):
    def test_segmento_livre_reconstroi_exatamente_os_vertices(self):
        vertices = [(20, 20), (70, 18), (82, 42), (55, 36), (40, 65), (18, 52)]
        led = criar_segmento_livre_por_pontos(vertices, "SEG_007")

        self.assertEqual(TIPO_ROI_SEGMENTO, led.tipo_roi)
        self.assertTrue(led.eh_segmento_livre)
        self.assertEqual("SEG_007", led.id)
        self.assertTrue(
            np.allclose(
                pontos_segmento(led),
                np.asarray(vertices, dtype=np.float32),
                atol=0.001,
            )
        )

    def test_segmento_convencional_continua_existindo(self):
        led = criar_segmento_por_arrasto(10, 10, 90, 25, id_roi="SEG_001")
        self.assertEqual(TIPO_ROI_SEGMENTO, led.tipo_roi)
        self.assertFalse(led.eh_segmento_livre)
        self.assertIsNone(led.pontos_segmento_livre)

    def test_segmento_livre_persiste_no_json(self):
        original = criar_segmento_livre_por_pontos(
            [(10, 10), (50, 10), (45, 35), (25, 25), (10, 40)],
            "SEG_003",
        ).com_normalizacao(100, 100)

        dados = original.to_dict()
        self.assertIn("pontos_segmento_livre", dados)
        restaurado = LedSelection.from_dict(dados)
        self.assertIsNotNone(restaurado)
        self.assertTrue(restaurado.eh_segmento_livre)
        self.assertTrue(
            np.allclose(
                pontos_segmento(restaurado),
                pontos_segmento(original),
                atol=0.001,
            )
        )

    def test_segmento_livre_adapta_vertices_para_nova_resolucao(self):
        original = criar_segmento_livre_por_pontos(
            [(10, 10), (40, 10), (45, 30), (20, 35)],
            "SEG_004",
        ).com_normalizacao(100, 100)
        adaptado = original.adaptar_para_resolucao(
            200,
            200,
            raio_minimo=2,
            raio_maximo=200,
        )
        self.assertTrue(
            np.allclose(
                pontos_segmento(adaptado),
                pontos_segmento(original) * 2.0,
                atol=1.0,
            )
        )

    def test_mascara_usa_poligono_real_inclusive_concavo(self):
        led = criar_segmento_livre_por_pontos(
            [(10, 10), (60, 10), (60, 60), (35, 35), (10, 60)],
            "SEG_005",
        )
        mascara = criar_mascara_roi_global(led, 80, 80)
        self.assertGreater(int(np.count_nonzero(mascara)), 0)
        self.assertTrue(ponto_dentro_roi(led, 20, 20))
        self.assertEqual(255, int(mascara[20, 20]))

    def test_copias_do_editor_e_guard_preservam_vertices(self):
        led = criar_segmento_livre_por_pontos(
            [(12, 12), (55, 12), (50, 40), (12, 45)],
            "SEG_006",
        )
        copia_editor = bulk_roi_editor.copiar_led(led)
        copia_guard = copiar_mascara_absoluta_segmento_livre(led)
        self.assertEqual(led.pontos_segmento_livre, copia_editor.pontos_segmento_livre)
        self.assertEqual(led.pontos_segmento_livre, copia_guard.pontos_segmento_livre)

    def test_assinatura_muda_quando_vertice_muda(self):
        led_a = criar_segmento_livre_por_pontos(
            [(10, 10), (50, 10), (50, 40), (10, 40)],
            "SEG_008",
        )
        led_b = LedSelection.from_dict(led_a.to_dict())
        self.assertIsNotNone(led_b)
        led_b.pontos_segmento_livre[0] = (
            led_b.pontos_segmento_livre[0][0] + 2.0,
            led_b.pontos_segmento_livre[0][1],
        )
        self.assertNotEqual(
            assinatura_geometria_segmento_livre([led_a]),
            assinatura_geometria_segmento_livre([led_b]),
        )

    def test_perfil_final_inclui_desenho_livre_antes_do_fullscreen(self):
        mro = RaspberryPi3ProductionApp.__mro__
        self.assertIn(FreeformSegmentDrawingMixin, mro)
        self.assertLess(
            mro.index(FreeformSegmentDrawingMixin),
            mro.index(FullscreenLedSelectionMixin),
        )

    def test_interacao_tem_linha_dinamica_e_fechamento_proximo_da_origem(self):
        fonte = inspect.getsource(FreeformSegmentDrawingMixin)
        self.assertIn("Segmento por pontos", fonte)
        self.assertIn("_evento_motion_selecao", fonte)
        self.assertIn("_segmento_livre_mouse", fonte)
        self.assertIn("FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX", fonte)
        self.assertGreaterEqual(FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX, 12)
        self.assertLessEqual(FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX, 24)


if __name__ == "__main__":
    unittest.main()
