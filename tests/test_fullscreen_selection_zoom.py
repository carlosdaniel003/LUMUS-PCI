import unittest

import numpy as np

from src.models.led_selection import LedSelection
from src.platform.fullscreen_led_selection import (
    CTRL_MASK,
    FullscreenLedSelectionMixin,
)
from src.platform.reference_capture import (
    ReferenceCaptureMixin,
    atualizar_configuracao_referencia,
    recortar_referencia_roi,
)


class FakeEvent:
    def __init__(self, x=800, y=450, delta=0, num=None, state=0):
        self.x = x
        self.y = y
        self.delta = delta
        self.num = num
        self.state = state


class FakeCanvas:
    def __init__(self):
        self.bindings = {}
        self.cursor = "crosshair"

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def configure(self, **kwargs):
        if "cursor" in kwargs:
            self.cursor = kwargs["cursor"]

    def focus_set(self):
        return None

    def winfo_width(self):
        return 1600

    def winfo_height(self):
        return 900


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas()
        self.imagem_canvas_original = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.rotacao_visual_principal = 0
        self.escala_exibicao = 1600 / 1920
        self.largura_imagem_exibida = 1600
        self.altura_imagem_exibida = 900
        self.deslocamento_imagem_x = 0
        self.deslocamento_imagem_y = 0
        self._selecao_zoom_ativo = True
        self._selecao_zoom_fator = 1.0
        self._selecao_zoom_centro_visual_x = None
        self._selecao_zoom_centro_visual_y = None
        self.redraws = 0
        self.draws = 0
        self.status = ""

    def obter_tamanho_canvas_principal(self):
        return 1600, 900

    def atualizar_imagem_principal_redimensionada(self):
        self.redraws += 1

    def desenhar_canvas(self, _leds, _resultados):
        self.draws += 1

    def limpar_lupa_canvas(self, _evento=None):
        return None

    def atualizar_status(self, texto):
        self.status = texto

    def evento_redimensionar_canvas_principal(self, _evento=None):
        return None

    def atualizar_lupa_canvas(self, _evento=None):
        return None


class FakeBase:
    def __init__(self):
        self.view = FakeView()
        self.leds_selecionados = []
        self.resultados_led_atual = []
        self.radius_events = 0

    def _evento_roda_roi(self, _evento=None):
        self.radius_events += 1
        return "break"


class FakeApp(FullscreenLedSelectionMixin, FakeBase):
    pass


class FakeReferenceBase:
    def __init__(self):
        self.modo_atual = "ocioso"
        self.leds_selecionados = []
        self.resultados_led_atual = []

    def _modo_edicao_roi_ativo(self):
        return False

    def _leds_editaveis(self):
        return list(self.leds_selecionados)

    def _substituir_leds_editaveis(self, leds):
        self.leds_selecionados = list(leds)


class FakeReferenceApp(ReferenceCaptureMixin, FakeReferenceBase):
    pass


class FullscreenSelectionZoomTests(unittest.TestCase):
    def test_scroll_sem_ctrl_continua_indo_para_editor_da_roi(self):
        app = FakeApp()
        evento = FakeEvent(delta=120, state=0)

        retorno = app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual("break", retorno)
        self.assertEqual(1, app.radius_events)
        self.assertEqual(1.0, app.view._selecao_zoom_fator)

    def test_ctrl_scroll_aplica_zoom_sem_alterar_raio(self):
        app = FakeApp()
        evento = FakeEvent(delta=120, state=CTRL_MASK)

        retorno = app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual("break", retorno)
        self.assertEqual(0, app.radius_events)
        self.assertGreater(app.view._selecao_zoom_fator, 1.0)
        self.assertEqual(1, app.view.redraws)
        self.assertEqual(1, app.view.draws)
        self.assertIn("Ctrl+scroll", app.view.status)
        self.assertIn("botão do meio", app.view.status)

    def test_scroll_linux_ctrl_button4_tambem_aplica_zoom(self):
        app = FakeApp()
        evento = FakeEvent(delta=0, num=4, state=CTRL_MASK)

        app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual(0, app.radius_events)
        self.assertGreater(app.view._selecao_zoom_fator, 1.0)

    def test_bindings_de_scroll_usam_despachante_zoom_ou_roi(self):
        app = FakeApp()
        canvas = FakeCanvas()

        app._configurar_eventos_canvas_tela_cheia(canvas)

        for sequencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.assertIn(sequencia, canvas.bindings)
            self.assertEqual(
                "_evento_roda_ou_zoom_selecao",
                canvas.bindings[sequencia].__name__,
            )

    def test_bindings_do_botao_do_meio_controlam_pan(self):
        app = FakeApp()
        canvas = FakeCanvas()

        app._configurar_eventos_canvas_tela_cheia(canvas)

        esperados = {
            "<Button-2>": "_evento_iniciar_pan_selecao",
            "<B2-Motion>": "_evento_arrastar_pan_selecao",
            "<ButtonRelease-2>": "_evento_finalizar_pan_selecao",
        }
        for sequencia, callback in esperados.items():
            self.assertIn(sequencia, canvas.bindings)
            self.assertEqual(callback, canvas.bindings[sequencia].__name__)

    def test_botao_do_meio_arrasta_imagem_quando_ha_zoom(self):
        app = FakeApp()
        app.view._selecao_zoom_fator = 2.0
        app.view.escala_exibicao = 2.0
        app.view.largura_imagem_exibida = 3840
        app.view.altura_imagem_exibida = 2160
        app.view.deslocamento_imagem_x = -1120
        app.view.deslocamento_imagem_y = -630
        app.view._selecao_zoom_centro_visual_x = 960.0
        app.view._selecao_zoom_centro_visual_y = 540.0

        retorno_inicio = app._evento_iniciar_pan_selecao(FakeEvent(x=800, y=450))
        retorno_arraste = app._evento_arrastar_pan_selecao(FakeEvent(x=900, y=410))

        self.assertEqual("break", retorno_inicio)
        self.assertEqual("break", retorno_arraste)
        self.assertTrue(app._selecao_pan_ativo)
        self.assertEqual("fleur", app.view.canvas.cursor)
        self.assertAlmostEqual(910.0, app.view._selecao_zoom_centro_visual_x)
        self.assertAlmostEqual(560.0, app.view._selecao_zoom_centro_visual_y)
        self.assertEqual(1, app.view.redraws)
        self.assertEqual(1, app.view.draws)

        retorno_fim = app._evento_finalizar_pan_selecao(FakeEvent(x=900, y=410))
        self.assertEqual("break", retorno_fim)
        self.assertFalse(app._selecao_pan_ativo)
        self.assertEqual("crosshair", app.view.canvas.cursor)

    def test_pan_na_borda_nao_cria_zona_morta(self):
        app = FakeApp()
        app.view._selecao_zoom_fator = 2.0
        app.view.escala_exibicao = 2.0
        app.view.largura_imagem_exibida = 3840
        app.view.altura_imagem_exibida = 2160
        app.view.deslocamento_imagem_x = 0
        app.view.deslocamento_imagem_y = 0
        app.view._selecao_zoom_centro_visual_x = 0.0
        app.view._selecao_zoom_centro_visual_y = 0.0

        app._evento_iniciar_pan_selecao(FakeEvent(x=100, y=100))
        app._evento_arrastar_pan_selecao(FakeEvent(x=0, y=100))

        self.assertAlmostEqual(450.0, app.view._selecao_zoom_centro_visual_x)

    def test_botao_do_meio_sem_zoom_nao_inicia_pan(self):
        app = FakeApp()

        retorno = app._evento_iniciar_pan_selecao(FakeEvent(x=800, y=450))
        app._evento_arrastar_pan_selecao(FakeEvent(x=900, y=450))

        self.assertEqual("break", retorno)
        self.assertFalse(app._selecao_pan_ativo)
        self.assertEqual("crosshair", app.view.canvas.cursor)
        self.assertEqual(0, app.view.redraws)
        self.assertEqual(0, app.view.draws)

    def test_recorte_referencia_circular_usa_geometria_da_roi(self):
        imagem = np.zeros((120, 160, 3), dtype=np.uint8)
        roi = LedSelection(
            id="REF_CIRCULO",
            centro_x=80,
            centro_y=60,
            raio=10,
            tipo_roi="circulo",
        )

        recorte = recortar_referencia_roi(imagem, roi)

        self.assertIsNotNone(recorte)
        self.assertGreater(recorte.shape[0], 20)
        self.assertGreater(recorte.shape[1], 20)

    def test_recorte_referencia_aceita_segmento_rotacionado(self):
        imagem = np.zeros((180, 220, 3), dtype=np.uint8)
        roi = LedSelection(
            id="SEG_REF",
            centro_x=110,
            centro_y=90,
            raio=35,
            tipo_roi="segmento",
            largura=70,
            altura=16,
            angulo=37.0,
        )

        recorte = recortar_referencia_roi(imagem, roi)

        self.assertIsNotNone(recorte)
        self.assertGreater(recorte.shape[0], 20)
        self.assertGreater(recorte.shape[1], 40)

    def test_recorte_referencia_rejeita_roi_fora_da_imagem(self):
        imagem = np.zeros((60, 60, 3), dtype=np.uint8)
        roi = LedSelection(
            id="REF_INVALIDA",
            centro_x=2,
            centro_y=2,
            raio=10,
            tipo_roi="circulo",
        )

        recorte = recortar_referencia_roi(imagem, roi)

        self.assertIsNone(recorte)

    def test_modo_referencia_e_editor_roi_real_e_limita_uma_roi(self):
        app = FakeReferenceApp()
        app._referencia_captura_tipo = "aceso"
        app.modo_atual = app.MODO_CAPTURA_REFERENCIA
        primeira = LedSelection(
            id="SEG_001",
            centro_x=40,
            centro_y=40,
            raio=20,
            tipo_roi="segmento",
            largura=40,
            altura=12,
            angulo=0,
        )
        segunda = LedSelection(
            id="SEG_002",
            centro_x=80,
            centro_y=60,
            raio=22,
            tipo_roi="segmento",
            largura=44,
            altura=12,
            angulo=15,
        )

        self.assertTrue(app._modo_edicao_roi_ativo())
        app._substituir_leds_editaveis([primeira, segunda])

        self.assertEqual(1, len(app.leds_selecionados))
        self.assertEqual("SEG_002", app.leds_selecionados[0].id)

    def test_referencia_individual_preserva_dados_e_geometria_da_roi(self):
        configuracao = {
            "fixed_leds": [{"id": "SEG_001"}],
            "settings": {"camera": {"fps": 20}},
            "reference_on": {
                "image_path": "aceso.png",
                "features": {"v_mean": 250.0},
            },
        }
        roi = LedSelection(
            id="SEG_REF",
            centro_x=120,
            centro_y=80,
            raio=30,
            tipo_roi="segmento",
            largura=58,
            altura=14,
            angulo=22.5,
        )

        atualizada = atualizar_configuracao_referencia(
            configuracao=configuracao,
            chave_referencia="reference_low_light",
            caminho_imagem="pouca_luz.png",
            features={"v_mean": 180.0},
            raio_atual_px=15,
            roi=roi.to_dict(),
        )

        self.assertEqual([{"id": "SEG_001"}], atualizada["fixed_leds"])
        self.assertEqual(
            "aceso.png",
            atualizada["reference_on"]["image_path"],
        )
        self.assertEqual(
            "pouca_luz.png",
            atualizada["reference_low_light"]["image_path"],
        )
        self.assertEqual(
            "segmento",
            atualizada["reference_low_light"]["roi"]["tipo_roi"],
        )
        self.assertAlmostEqual(
            22.5,
            atualizada["reference_low_light"]["roi"]["angulo"],
        )
        self.assertEqual(15, atualizada["default_radius_px"])


if __name__ == "__main__":
    unittest.main()
