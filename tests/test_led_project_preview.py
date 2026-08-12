import inspect
import unittest

from src.models.led_selection import LedSelection
from src.platform.led_project_preview import (
    LedProjectPreviewMixin,
    calcular_transformacao_preview,
)
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp


class LedProjectPreviewMathTests(unittest.TestCase):
    def test_preview_preserva_proporcao_da_base_1080p(self):
        led = LedSelection(
            id="SEG_001",
            centro_x=960,
            centro_y=540,
            raio=20,
        )
        escala, offset_x, offset_y, largura, altura = calcular_transformacao_preview(
            [led],
            largura_canvas=220,
            altura_canvas=150,
            largura_base=1920,
            altura_base=1080,
        )

        self.assertAlmostEqual(200.0 / 1920.0, escala, places=6)
        self.assertAlmostEqual(10.0, offset_x, places=4)
        self.assertAlmostEqual(18.75, offset_y, places=4)
        self.assertEqual(1920, largura)
        self.assertEqual(1080, altura)

    def test_roi_fora_da_base_expande_preview_sem_cortar(self):
        led = LedSelection(
            id="SEG_FORA",
            centro_x=2050,
            centro_y=1180,
            raio=30,
        )
        _escala, _offset_x, _offset_y, largura, altura = calcular_transformacao_preview(
            [led],
            largura_canvas=220,
            altura_canvas=150,
            largura_base=1920,
            altura_base=1080,
        )

        self.assertGreaterEqual(largura, 2090)
        self.assertGreaterEqual(altura, 1220)

    def test_segmento_rotacionado_participa_dos_limites(self):
        led = LedSelection(
            id="SEG_ROT",
            centro_x=1900,
            centro_y=1040,
            raio=10,
            tipo_roi="segmento",
            largura=180,
            altura=30,
            angulo=45,
        )
        _escala, _offset_x, _offset_y, largura, altura = calcular_transformacao_preview(
            [led],
            largura_canvas=220,
            altura_canvas=150,
            largura_base=1920,
            altura_base=1080,
        )

        self.assertGreater(largura, 1920)
        self.assertGreater(altura, 1080)


class LedProjectPreviewIntegrationTests(unittest.TestCase):
    def test_perfil_display_inclui_mixin_de_preview(self):
        mro = RaspberryPi3ProductionApp.__mro__
        self.assertIn(LedProjectPreviewMixin, mro)

    def test_preview_intercepta_seletor_e_delega_fluxo_existente(self):
        fonte = inspect.getsource(
            LedProjectPreviewMixin._selecionar_projeto_led_existente
        )
        self.assertIn("_instalar_preview_gerenciador_leds", fonte)
        self.assertIn("super()._selecionar_projeto_led_existente", fonte)

    def test_preview_acompanha_selecao_sem_mudar_lista(self):
        fonte = inspect.getsource(
            LedProjectPreviewMixin._instalar_preview_gerenciador_leds
        )
        self.assertIn('"<<ListboxSelect>>"', fonte)
        self.assertIn("acompanhar_selecao", fonte)
        self.assertIn("carregar_leds_fixos(projeto=nome)", fonte)


if __name__ == "__main__":
    unittest.main()
