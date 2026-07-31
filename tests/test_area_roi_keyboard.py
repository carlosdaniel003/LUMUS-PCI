import unittest

import numpy as np

from src.models.led_selection import LedSelection
from src.platform.area_roi_editor_v4 import AreaRoiEditorV4Mixin


class FakeEvent:
    def __init__(self, x=0, y=0, keysym="", delta=0, num=None):
        self.x = x
        self.y = y
        self.keysym = keysym
        self.delta = delta
        self.num = num
        self.state = 0


class FakeRoot:
    def __init__(self):
        self.bindings = {}

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def after_cancel(self, _after_id):
        return None


class FakeCanvas:
    def __init__(self):
        self.bindings = {}
        self.items = []

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def focus_set(self):
        return None

    def delete(self, _tag):
        return None

    def create_oval(self, *args, **kwargs):
        self.items.append(("oval", args, kwargs))

    def create_rectangle(self, *args, **kwargs):
        self.items.append(("rectangle", args, kwargs))

    def create_text(self, *args, **kwargs):
        self.items.append(("text", args, kwargs))

    def tag_raise(self, _tag):
        return None


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas()
        self.escala_exibicao = 1.0
        self.deslocamento_imagem_x = 0
        self.deslocamento_imagem_y = 0
        self.selecao_manual_camera_visivel = False
        self.selecao_led_ativa = True
        self.raio_atual_px = 12
        self.imagem_canvas_original = np.zeros((480, 640, 3), dtype=np.uint8)
        self.status = ""
        self.preview_calls = []
        self.draw_calls = 0

    def converter_canvas_para_imagem_original(self, x, y):
        if 0 <= x < 640 and 0 <= y < 480:
            return int(x), int(y)
        return None

    def desenhar_canvas(self, *_args, **_kwargs):
        self.draw_calls += 1

    def desenhar_lupa_canvas(self, **kwargs):
        self.preview_calls.append((kwargs["imagem_x"], kwargs["imagem_y"]))

    def obter_tamanho_canvas_principal(self):
        return 640, 480

    def atualizar_status(self, texto):
        self.status = texto

    def atualizar_faixa_resultado(self):
        return None


class FakeBaseApp:
    def __init__(self):
        self.root = FakeRoot()
        self.view = FakeView()
        self.modo_atual = "selecionar_leds_analise"
        self.largura_original = 640
        self.altura_original = 480
        self.leds_selecionados = [
            LedSelection("LED_001", 100, 100, 10),
            LedSelection("LED_002", 200, 100, 10),
            LedSelection("LED_003", 320, 220, 12),
        ]
        self.leds_manuais_camera = []
        self.resultados_led_atual = []
        self.camera_ativa = False
        self.guias_leds_fixos_visiveis = False

    def evento_clique_esquerdo(self, evento):
        self.leds_selecionados.append(
            LedSelection(
                f"LED_{len(self.leds_selecionados) + 1:03d}",
                int(evento.x),
                int(evento.y),
                12,
            )
        )
        return "base"

    def atualizar_renderizacoes_visuais(self, *_args, **_kwargs):
        return None

    def atualizar_renderizacoes_camera_se_necessario(self, *_args, **_kwargs):
        return None

    def atualizar_painel_inicial(self):
        return None

    def iniciar_selecao_led(self):
        return None

    def configurar_leds_fixos(self):
        return None

    def carregar_imagem(self):
        return None

    def carregar_leds_fixos(self):
        return None

    def limpar_tela(self):
        return None


class FakeAreaKeyboardApp(AreaRoiEditorV4Mixin, FakeBaseApp):
    pass


class AreaRoiKeyboardTests(unittest.TestCase):
    def selecionar_roi_individual(self, app):
        evento = FakeEvent(100, 100)
        app.evento_clique_esquerdo(evento)
        app._evento_soltar_roi(evento)

    def selecionar_duas_primeiras(self, app):
        app.evento_clique_esquerdo(FakeEvent(70, 70))
        app._evento_arrastar_roi(FakeEvent(230, 130))
        app._evento_soltar_roi(FakeEvent(230, 130))

    def test_setas_sao_vinculadas_ao_canvas(self):
        app = FakeAreaKeyboardApp()

        for sequencia in ("<Left>", "<Right>", "<Up>", "<Down>"):
            self.assertIn(sequencia, app.view.canvas.bindings)

    def test_seta_move_roi_individual_um_pixel(self):
        app = FakeAreaKeyboardApp()
        self.selecionar_roi_individual(app)

        retorno = app._evento_mover_roi_teclado(FakeEvent(keysym="Right"))
        por_id = {led.id: led for led in app.leds_selecionados}

        self.assertEqual("break", retorno)
        self.assertEqual((101, 100), (
            por_id["LED_001"].centro_x,
            por_id["LED_001"].centro_y,
        ))
        self.assertEqual((200, 100), (
            por_id["LED_002"].centro_x,
            por_id["LED_002"].centro_y,
        ))

    def test_seta_move_subconjunto_selecionado_um_pixel(self):
        app = FakeAreaKeyboardApp()
        self.selecionar_duas_primeiras(app)

        app._evento_mover_roi_teclado(FakeEvent(keysym="Down"))
        por_id = {led.id: led for led in app.leds_selecionados}

        self.assertEqual(101, por_id["LED_001"].centro_y)
        self.assertEqual(101, por_id["LED_002"].centro_y)
        self.assertEqual(220, por_id["LED_003"].centro_y)

    def test_seta_respeita_limite_da_imagem(self):
        app = FakeAreaKeyboardApp()
        app.leds_selecionados = [
            LedSelection("LED_001", 10, 100, 10),
        ]
        app._selecionar_ids(["LED_001"], mensagem=False)

        app._evento_mover_roi_teclado(FakeEvent(keysym="Left"))

        self.assertEqual(10, app.leds_selecionados[0].centro_x)
        self.assertIn("bloqueado", app.view.status)

    def test_preview_atualiza_depois_da_seta(self):
        app = FakeAreaKeyboardApp()
        self.selecionar_roi_individual(app)
        chamadas_antes = len(app.view.preview_calls)

        app._evento_mover_roi_teclado(FakeEvent(keysym="Up"))

        self.assertGreater(len(app.view.preview_calls), chamadas_antes)
        self.assertEqual((100, 99), app.view.preview_calls[-1])


if __name__ == "__main__":
    unittest.main()
