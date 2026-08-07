import inspect
import unittest

import numpy as np

import src.ui.main_window_parts.magnifier.desenhar_lupa_canvas as lupa_module
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp
from src.platform.rotated_preview_roi_editor import (
    RotatedPreviewAreaRoiEditorMixin,
    converter_ponto_preview_lupa,
    converter_retangulo_preview_lupa,
)
from src.ui.main_window_parts.magnifier.desenhar_lupa_canvas import (
    rotacionar_preview_lupa,
)


class RotatedMagnifierTests(unittest.TestCase):
    def test_preview_gira_90_sem_mudar_fonte(self):
        imagem = np.array(
            [
                [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
                [[4, 4, 4], [5, 5, 5], [6, 6, 6]],
            ],
            dtype=np.uint8,
        )
        original = imagem.copy()

        preview = rotacionar_preview_lupa(imagem, 90)

        self.assertTrue(np.array_equal(imagem, original))
        self.assertEqual((3, 2, 3), preview.shape)
        self.assertEqual(4, int(preview[0, 0, 0]))
        self.assertEqual(1, int(preview[0, 1, 0]))

    def test_preview_segue_quatro_orientacoes(self):
        imagem = np.arange(27, dtype=np.uint8).reshape((3, 3, 3))

        self.assertTrue(np.array_equal(rotacionar_preview_lupa(imagem, 0), imagem))
        self.assertTrue(
            np.array_equal(
                rotacionar_preview_lupa(imagem, 90),
                np.rot90(imagem, k=3),
            )
        )
        self.assertTrue(
            np.array_equal(
                rotacionar_preview_lupa(imagem, 180),
                np.rot90(imagem, k=2),
            )
        )
        self.assertTrue(
            np.array_equal(
                rotacionar_preview_lupa(imagem, 270),
                np.rot90(imagem, k=1),
            )
        )

    def test_ponto_do_overlay_da_lupa_gira_com_preview(self):
        self.assertEqual((190.0, 0.0), converter_ponto_preview_lupa(0, 0, 190, 90))
        self.assertEqual((190.0, 190.0), converter_ponto_preview_lupa(0, 0, 190, 180))
        self.assertEqual((0.0, 190.0), converter_ponto_preview_lupa(0, 0, 190, 270))

    def test_retangulo_do_marquee_tambem_gira(self):
        self.assertEqual(
            (130.0, 10.0, 170.0, 50.0),
            converter_retangulo_preview_lupa(10, 20, 50, 60, 190, 90),
        )
        self.assertEqual(
            (140.0, 130.0, 180.0, 170.0),
            converter_retangulo_preview_lupa(10, 20, 50, 60, 190, 180),
        )

    def test_perfil_final_usa_editor_com_preview_rotacionada(self):
        self.assertIn(RotatedPreviewAreaRoiEditorMixin, RaspberryPi3ProductionApp.__mro__)

    def test_lupa_nao_altera_camera_ou_mascaras(self):
        codigo = inspect.getsource(lupa_module)
        self.assertNotIn("camera_service", codigo)
        self.assertNotIn("config_repository", codigo)
        self.assertNotIn("salvar_leds_fixos", codigo)
        self.assertNotIn("leds_fixos_configurados =", codigo)


if __name__ == "__main__":
    unittest.main()
