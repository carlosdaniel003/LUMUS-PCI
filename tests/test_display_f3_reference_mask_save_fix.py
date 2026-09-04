import inspect
import unittest

from src.platform.display_f3_reference_mask_save_fix import (
    instalar_correcao_salvamento_mascara_referencia_display_f3,
    normalizar_mascara_referencia_editor_f3,
)


class DisplayF3ReferenceMaskSaveFixTests(unittest.TestCase):
    def test_segmento_desenhado_permanece_uma_mascara_valida(self):
        mask = {
            "id": "MASK_001",
            "type": "segment",
            "cx": 901,
            "cy": 442,
            "width": 48,
            "height": 17,
            "angle": -87.5,
        }

        normalized = normalizar_mascara_referencia_editor_f3(mask)

        self.assertIsNotNone(normalized)
        self.assertEqual("segment", normalized["type"])
        self.assertEqual(901, normalized["cx"])
        self.assertEqual(442, normalized["cy"])
        self.assertEqual(48, normalized["width"])
        self.assertEqual(17, normalized["height"])
        self.assertAlmostEqual(-87.5, normalized["angle"])

    def test_segmento_invalido_nao_e_aceito(self):
        mask = {
            "id": "MASK_001",
            "type": "segment",
            "cx": 100,
            "cy": 100,
            "width": 0,
            "height": 14,
            "angle": 0,
        }
        self.assertIsNone(normalizar_mascara_referencia_editor_f3(mask))

    def test_circulo_e_poligono_continuam_compativeis(self):
        circle = normalizar_mascara_referencia_editor_f3(
            {"id": "C", "type": "circle", "cx": 10, "cy": 20, "radius": 7}
        )
        polygon = normalizar_mascara_referencia_editor_f3(
            {"id": "P", "type": "polygon", "points": [[0, 0], [10, 0], [5, 8]]}
        )
        self.assertEqual("circle", circle["type"])
        self.assertEqual("polygon", polygon["type"])
        self.assertEqual(3, len(polygon["points"]))

    def test_instalador_e_exclusivo_do_editor_referencia_f3(self):
        instalar_correcao_salvamento_mascara_referencia_display_f3()
        source = inspect.getsource(
            __import__(
                "src.platform.display_f3_reference_mask_save_fix",
                fromlist=["dummy"],
            )
        )
        self.assertNotIn("f2_", source.lower())
        self.assertNotIn("led_mask_editor", source)


if __name__ == "__main__":
    unittest.main()
