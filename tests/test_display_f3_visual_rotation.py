from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace

import numpy as np

from src.platform.display_production_f3 import DisplayProductionF3Mixin
from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.display_project_config import DisplayProjectConfigWindow
from src.platform.display_visual_rotation import (
    obter_rotacao_visual_display,
    preparar_frame_visual_display,
    preparar_mascara_visual_display,
    restaurar_mascara_original_display,
)


class DisplayF3VisualRotationTests(unittest.TestCase):
    def test_le_rotacao_visual_atual_da_view(self):
        for angle in (0, 90, 180, 270):
            view = SimpleNamespace(rotacao_visual_principal=angle)
            self.assertEqual(angle, obter_rotacao_visual_display(view))

    def test_rotacao_90_troca_dimensoes_sem_modificar_frame_original(self):
        frame = np.zeros((2, 3, 3), dtype=np.uint8)
        frame[0, 0] = (10, 20, 30)
        original = frame.copy()

        rotated = preparar_frame_visual_display(frame, 90)

        self.assertEqual((3, 2, 3), rotated.shape)
        np.testing.assert_array_equal(original, frame)
        self.assertFalse(np.shares_memory(frame, rotated))

    def test_rotacao_180_preserva_dimensoes_e_fonte(self):
        frame = np.arange(4 * 7 * 3, dtype=np.uint8).reshape(4, 7, 3)
        original = frame.copy()
        rotated = preparar_frame_visual_display(frame, 180)

        self.assertEqual(frame.shape, rotated.shape)
        np.testing.assert_array_equal(original, frame)

    def test_mascara_editada_na_orientacao_visual_volta_para_coordenadas_mestre(self):
        original = {
            "id": "MASK_001",
            "type": "circle",
            "cx": 120,
            "cy": 80,
            "radius": 14,
        }

        for angle in (90, 180, 270):
            visual = preparar_mascara_visual_display(
                original,
                640,
                480,
                angle,
            )
            restored = restaurar_mascara_original_display(
                visual,
                640,
                480,
                angle,
            )
            self.assertEqual(original, restored)

    def test_editor_visual_de_mascaras_f3_usa_rotacao_visual(self):
        source = inspect.getsource(DisplayProjectConfigWindow.edit_masks)
        self.assertIn("preparar_check_visual_display", source)
        self.assertIn("frame_visual", source)
        self.assertIn("resolution_visual", source)
        self.assertIn("masks_visual", source)
        self.assertIn("restaurar_mascara_original_display", source)

    def test_runtime_f3_encaminha_rotacao_da_tela_principal(self):
        class FakeWindow:
            def __init__(self):
                self.calls = []

            def update_camera_preview(self, frame, visual_rotation=0):
                self.calls.append((frame, visual_rotation))
                return True

        app = DisplayProductionF3Mixin.__new__(DisplayProductionF3Mixin)
        app.display_f3_after_id = None
        app.display_f3_ativo = True
        app.display_f3_window = FakeWindow()
        app.camera_frame_atual = np.zeros((4, 6, 3), dtype=np.uint8)
        app.view = SimpleNamespace(rotacao_visual_principal=270)
        app._agendar_preview_display_f3 = lambda *args, **kwargs: None

        app._atualizar_preview_display_f3()

        self.assertEqual(1, len(app.display_f3_window.calls))
        frame_recebido, rotacao = app.display_f3_window.calls[0]
        self.assertIs(frame_recebido, app.camera_frame_atual)
        self.assertEqual(270, rotacao)

    def test_janela_f3_aplica_rotacao_somente_antes_do_preview(self):
        source = inspect.getsource(DisplayProductionF3Window.update_camera_preview)
        self.assertIn("preparar_frame_visual_display", source)
        self.assertIn("self.update_preview(visual_frame, leds=())", source)
        self.assertNotIn("camera_service", source)
        self.assertNotIn("operacao_engine", source)

    def test_mixin_f3_nao_sobrescreve_rotacao_da_view_f2(self):
        self.assertNotIn(
            "rotacionar_imagem_principal",
            DisplayProductionF3Mixin.__dict__,
        )
        self.assertNotIn(
            "definir_rotacao_visual_principal",
            DisplayProductionF3Mixin.__dict__,
        )


if __name__ == "__main__":
    unittest.main()
