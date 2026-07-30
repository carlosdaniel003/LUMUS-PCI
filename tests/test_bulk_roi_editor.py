import unittest

from src.models.led_selection import LedSelection
from src.platform.bulk_roi_editor import (
    BulkRoiEditorMixin,
    ajustar_raios_rois,
    escalar_rois_uniformemente,
    limitar_deslocamento_rois,
    mover_rois,
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
        self.after_callbacks = {}
        self.cancelled = []
        self._next = 0

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def after(self, _delay, callback):
        self._next += 1
        after_id = f"after-{self._next}"
        self.after_callbacks[after_id] = callback
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)
        self.after_callbacks.pop(after_id, None)


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


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas()
        self.escala_exibicao = 1.0
        self.deslocamento_imagem_x = 0
        self.deslocamento_imagem_y = 0
        self.selecao_manual_camera_visivel = False
        self.status = ""
        self.draw_calls = 0

    def converter_canvas_para_imagem_original(self, x, y):
        return int(x), int(y)

    def desenhar_canvas(self, *_args, **_kwargs):
        self.draw_calls += 1

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
            LedSelection("LED_001", 100, 100, 12),
            LedSelection("LED_002", 200, 100, 12),
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


class FakeBulkApp(BulkRoiEditorMixin, FakeBaseApp):
    pass


class BulkRoiGeometryTests(unittest.TestCase):
    def test_movimento_preserva_distancias_relativas(self):
        origem = [
            LedSelection("A", 100, 100, 10),
            LedSelection("B", 180, 130, 15),
        ]
        movidos = mover_rois(origem, 25, -20, 640, 480)

        self.assertEqual((125, 80), (movidos[0].centro_x, movidos[0].centro_y))
        self.assertEqual((205, 110), (movidos[1].centro_x, movidos[1].centro_y))
        self.assertEqual(80, movidos[1].centro_x - movidos[0].centro_x)
        self.assertEqual(30, movidos[1].centro_y - movidos[0].centro_y)

    def test_movimento_coletivo_para_na_borda(self):
        origem = [
            LedSelection("A", 20, 20, 10),
            LedSelection("B", 80, 40, 10),
        ]
        dx, dy = limitar_deslocamento_rois(origem, -100, -100, 320, 240)
        self.assertEqual((-10, -10), (dx, dy))

        movidos = mover_rois(origem, -100, -100, 320, 240)
        self.assertEqual((10, 10), (movidos[0].centro_x, movidos[0].centro_y))

    def test_escala_posicoes_e_raios_uniformemente(self):
        origem = [
            LedSelection("A", 100, 100, 10),
            LedSelection("B", 200, 100, 20),
        ]
        escalados = escalar_rois_uniformemente(
            origem,
            centro_grupo_x=150,
            centro_grupo_y=100,
            escala_desejada=1.5,
            largura=640,
            altura=480,
        )

        self.assertEqual((75, 100, 15), (
            escalados[0].centro_x,
            escalados[0].centro_y,
            escalados[0].raio,
        ))
        self.assertEqual((225, 100, 30), (
            escalados[1].centro_x,
            escalados[1].centro_y,
            escalados[1].raio,
        ))

    def test_escala_nao_deixa_roi_sair_da_imagem(self):
        origem = [
            LedSelection("A", 30, 30, 10),
            LedSelection("B", 290, 210, 10),
        ]
        escalados = escalar_rois_uniformemente(
            origem,
            centro_grupo_x=160,
            centro_grupo_y=120,
            escala_desejada=3.0,
            largura=320,
            altura=240,
        )

        for led in escalados:
            self.assertGreaterEqual(led.centro_x - led.raio, 0)
            self.assertGreaterEqual(led.centro_y - led.raio, 0)
            self.assertLess(led.centro_x + led.raio, 320)
            self.assertLess(led.centro_y + led.raio, 240)

    def test_ajuste_de_raio_respeita_limites_e_bordas(self):
        origem = [
            LedSelection("A", 8, 8, 6),
            LedSelection("B", 100, 100, 20),
        ]
        maiores = ajustar_raios_rois(origem, 50, 320, 240)
        self.assertEqual(8, maiores[0].raio)
        self.assertLessEqual(maiores[1].raio, 100)

        menores = ajustar_raios_rois(origem, -100, 320, 240)
        self.assertTrue(all(led.raio >= 3 for led in menores))


class BulkRoiInteractionTests(unittest.TestCase):
    def test_clique_curto_no_vazio_continua_adicionando_roi(self):
        app = FakeBulkApp()
        evento = FakeEvent(350, 300)

        self.assertEqual("break", app.evento_clique_esquerdo(evento))
        self.assertEqual(0, app.base_clicks)

        retorno = app._evento_soltar_roi(evento)

        self.assertEqual("base", retorno)
        self.assertEqual(1, app.base_clicks)
        self.assertEqual(3, len(app.leds_selecionados))

    def test_clique_em_roi_seleciona_individual_sem_criar_duplicata(self):
        app = FakeBulkApp()
        evento = FakeEvent(100, 100)

        app.evento_clique_esquerdo(evento)

        self.assertEqual("single", app._roi_editor_selection)
        self.assertEqual("LED_001", app._roi_editor_single_id)
        self.assertEqual(0, app.base_clicks)
        self.assertEqual(2, len(app.leds_selecionados))

    def test_shift_clique_no_vazio_seleciona_todas(self):
        app = FakeBulkApp()
        evento = FakeEvent(350, 300, state=0x0001)

        app.evento_clique_esquerdo(evento)

        self.assertEqual("all", app._roi_editor_selection)
        self.assertEqual("move_all", app._roi_editor_drag_mode)
        self.assertEqual(0, app.base_clicks)

    def test_delete_remove_apenas_roi_individual(self):
        app = FakeBulkApp()
        app.evento_clique_esquerdo(FakeEvent(100, 100))

        retorno = app._evento_apagar_roi()

        self.assertEqual("break", retorno)
        self.assertEqual(["LED_002"], [led.id for led in app.leds_selecionados])

    def test_delete_remove_todo_conjunto(self):
        app = FakeBulkApp()
        app._selecionar_todas_rois(mensagem=False)

        app._evento_apagar_roi()

        self.assertEqual([], app.leds_selecionados)


if __name__ == "__main__":
    unittest.main()
