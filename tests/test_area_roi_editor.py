import unittest

import numpy as np

from src.models.led_selection import LedSelection
from src.platform.area_roi_editor import (
    AreaRoiEditorMixin,
    escalar_rois_por_ancora,
    esticar_rois_em_eixo,
    selecionar_rois_por_area,
)


class FakeEvent:
    def __init__(self, x=0, y=0, state=0, delta=0, num=None):
        self.x = x
        self.y = y
        self.state = state
        self.delta = delta
        self.num = num


class FakeRoot:
    def __init__(self):
        self.bindings = {}
        self.cancelled = []

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)


class FakeCanvas:
    def __init__(self):
        self.bindings = {}
        self.items = []

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def focus_set(self):
        return None

    def delete(self, tag):
        self.items = [item for item in self.items if item[-1] != tag]

    def create_oval(self, *args, **kwargs):
        self.items.append(("oval", args, kwargs, kwargs.get("tags")))

    def create_rectangle(self, *args, **kwargs):
        self.items.append(("rectangle", args, kwargs, kwargs.get("tags")))

    def create_text(self, *args, **kwargs):
        self.items.append(("text", args, kwargs, kwargs.get("tags")))

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
        self.draw_calls = 0
        self.preview_calls = 0
        self.preview_positions = []

    def converter_canvas_para_imagem_original(self, x, y):
        if 0 <= x < 640 and 0 <= y < 480:
            return int(x), int(y)
        return None

    def desenhar_canvas(self, *_args, **_kwargs):
        self.draw_calls += 1

    def desenhar_lupa_canvas(self, **kwargs):
        self.preview_calls += 1
        self.preview_positions.append((kwargs["imagem_x"], kwargs["imagem_y"]))

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
        self.base_clicks = 0

    def evento_clique_esquerdo(self, evento):
        self.base_clicks += 1
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


class FakeAreaApp(AreaRoiEditorMixin, FakeBaseApp):
    pass


class AreaRoiGeometryTests(unittest.TestCase):
    def test_area_exige_roi_totalmente_englobada(self):
        leds = [
            LedSelection("A", 100, 100, 10),
            LedSelection("B", 200, 100, 10),
        ]
        selecionados = selecionar_rois_por_area(
            leds,
            90,
            90,
            205,
            115,
        )
        self.assertEqual(["A"], [led.id for led in selecionados])

    def test_escala_por_ancora_altera_posicoes_e_raios(self):
        leds = [
            LedSelection("A", 100, 100, 10),
            LedSelection("B", 200, 100, 20),
        ]
        resultado = escalar_rois_por_ancora(
            leds,
            ancora_x=50,
            ancora_y=100,
            fator_desejado=1.5,
            largura=640,
            altura=480,
        )
        self.assertEqual((125, 100, 15), (
            resultado[0].centro_x,
            resultado[0].centro_y,
            resultado[0].raio,
        ))
        self.assertEqual((275, 100, 30), (
            resultado[1].centro_x,
            resultado[1].centro_y,
            resultado[1].raio,
        ))

    def test_esticar_horizontal_preserva_raios(self):
        leds = [
            LedSelection("A", 100, 100, 10),
            LedSelection("B", 200, 100, 15),
        ]
        resultado = esticar_rois_em_eixo(
            leds,
            eixo="x",
            ancora=50,
            fator_desejado=1.5,
            largura=640,
            altura=480,
        )
        self.assertEqual((125, 10), (resultado[0].centro_x, resultado[0].raio))
        self.assertEqual((275, 15), (resultado[1].centro_x, resultado[1].raio))


class AreaRoiInteractionTests(unittest.TestCase):
    def _selecionar_duas_primeiras(self, app):
        app.evento_clique_esquerdo(FakeEvent(70, 70))
        app._evento_arrastar_roi(FakeEvent(230, 130))
        app._evento_soltar_roi(FakeEvent(230, 130))

    def test_arrasto_no_vazio_cria_seletor_sem_adicionar_roi(self):
        app = FakeAreaApp()
        self._selecionar_duas_primeiras(app)

        self.assertEqual(0, app.base_clicks)
        self.assertEqual(3, len(app.leds_selecionados))
        self.assertEqual({"LED_001", "LED_002"}, app._area_roi_ids)
        self.assertGreater(app.view.preview_calls, 0)
        self.assertEqual((230, 130), app.view.preview_positions[-1])

    def test_clique_curto_no_vazio_continua_adicionando_roi(self):
        app = FakeAreaApp()
        evento = FakeEvent(400, 300)
        app.evento_clique_esquerdo(evento)
        retorno = app._evento_soltar_roi(evento)

        self.assertEqual("base", retorno)
        self.assertEqual(1, app.base_clicks)
        self.assertEqual(4, len(app.leds_selecionados))
        self.assertEqual({"LED_004"}, app._area_roi_ids)

    def test_movimento_altera_apenas_rois_selecionadas(self):
        app = FakeAreaApp()
        self._selecionar_duas_primeiras(app)

        app.evento_clique_esquerdo(FakeEvent(150, 100))
        app._evento_arrastar_roi(FakeEvent(170, 120))
        app._evento_soltar_roi(FakeEvent(170, 120))

        posicoes = {
            led.id: (led.centro_x, led.centro_y)
            for led in app.leds_selecionados
        }
        self.assertEqual((120, 120), posicoes["LED_001"])
        self.assertEqual((220, 120), posicoes["LED_002"])
        self.assertEqual((320, 220), posicoes["LED_003"])
        self.assertGreaterEqual(app.view.preview_calls, 3)

    def test_handle_lateral_estica_subconjunto(self):
        app = FakeAreaApp()
        self._selecionar_duas_primeiras(app)
        handle_x, handle_y = app._handles_canvas()["e"]

        app.evento_clique_esquerdo(FakeEvent(int(handle_x), int(handle_y)))
        app._evento_arrastar_roi(FakeEvent(int(handle_x + 60), int(handle_y)))
        app._evento_soltar_roi(FakeEvent(int(handle_x + 60), int(handle_y)))

        por_id = {led.id: led for led in app.leds_selecionados}
        distancia = por_id["LED_002"].centro_x - por_id["LED_001"].centro_x
        self.assertGreater(distancia, 100)
        self.assertEqual(10, por_id["LED_001"].raio)
        self.assertEqual((320, 220), (
            por_id["LED_003"].centro_x,
            por_id["LED_003"].centro_y,
        ))

    def test_delete_remove_somente_subconjunto_selecionado(self):
        app = FakeAreaApp()
        self._selecionar_duas_primeiras(app)
        retorno = app._evento_apagar_roi()

        self.assertEqual("break", retorno)
        self.assertEqual(["LED_003"], [led.id for led in app.leds_selecionados])


if __name__ == "__main__":
    unittest.main()
