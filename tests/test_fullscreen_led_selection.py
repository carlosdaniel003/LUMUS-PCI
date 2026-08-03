import unittest

from src.models.led_selection import LedSelection
from src.platform.fixed_mask_geometry_guard import assinatura_geometria
from src.platform.fullscreen_led_selection import FullscreenLedSelectionMixin


class FakeEvent:
    def __init__(self, x=0, y=0, keysym=""):
        self.x = x
        self.y = y
        self.keysym = keysym
        self.delta = 0
        self.num = None
        self.state = 0


class FakeCanvas:
    def __init__(self, nome):
        self.nome = nome
        self.bindings = {}
        self.focus_calls = 0

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def focus_set(self):
        self.focus_calls += 1


class FakeWindow:
    def __init__(self):
        self.exists = True
        self.fullscreen = False
        self.destroyed = False
        self.protocols = {}
        self.grabbed = False
        self.after_calls = []

    def winfo_exists(self):
        return int(self.exists)

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def grab_set(self):
        self.grabbed = True

    def grab_release(self):
        self.grabbed = False

    def lift(self):
        return None

    def focus_force(self):
        return None

    def attributes(self, name, value):
        if name == "-fullscreen":
            self.fullscreen = bool(value)

    def geometry(self, _value):
        return None

    def after(self, delay, callback):
        self.after_calls.append(delay)
        callback()
        return f"after-{delay}"

    def destroy(self):
        self.destroyed = True
        self.exists = False


class FakeRoot:
    def __init__(self):
        self.cancelled = []

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class FakeCameraService:
    def __init__(self):
        self.update_calls = 0
        self.start_calls = 0
        self.stop_calls = 0

    def atualizar_configuracoes_camera(self, _settings):
        self.update_calls += 1

    def iniciar(self):
        self.start_calls += 1

    def parar(self):
        self.stop_calls += 1


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas("principal")
        self._redimensionamento_pendente = None
        self.imagem_tk = object()
        self._imagem_tk_largura = 640
        self._imagem_tk_altura = 360
        self._lupa_ultimo_tempo_s = 1.0
        self._lupa_ultima_posicao_canvas = (10, 10)
        self.selecao_led_ativa = False
        self.preparacoes = 0
        self.desenhos = 0
        self.preview_canvases = []
        self.status = ""

    def preparar_imagem_para_exibicao(self, _imagem):
        self.preparacoes += 1
        self.imagem_tk = object()

    def desenhar_canvas(self, _leds, _resultados):
        self.desenhos += 1

    def evento_redimensionar_canvas_principal(self, _evento=None):
        return None

    def atualizar_lupa_canvas(self, _evento=None):
        self.preview_canvases.append(self.canvas)

    def limpar_lupa_canvas(self, _evento=None):
        return None

    def atualizar_estado_selecao_led(self, ativa):
        self.selecao_led_ativa = bool(ativa)

    def atualizar_status(self, texto):
        self.status = texto


class FakeBaseApp:
    MODOS_EDICAO = {
        "selecionar_leds_analise",
        "selecionar_leds_camera",
        "configurar_leds_fixos",
    }

    def __init__(self):
        self.root = FakeRoot()
        self.view = FakeView()
        self.camera_service = FakeCameraService()
        self.camera_ativa = True
        self.configuracoes_camera = {
            "width": 1920,
            "height": 1080,
            "fps": 20,
            "format": "MJPG",
        }
        self.modo_atual = "tela_ao_vivo"
        self.imagem_original = object()
        self.leds_fixos_configurados = [
            LedSelection("LED_001", 900, 500, 18),
            LedSelection("LED_002", 1100, 520, 20),
        ]
        self.leds_selecionados = [
            LedSelection("LED_001", 900, 500, 18),
            LedSelection("LED_002", 1100, 520, 20),
        ]
        self.resultados_led_atual = []
        self.base_selection_calls = 0
        self.capture_calls = 0
        self.stop_calls = 0
        self.clear_calls = 0

    def _modo_edicao_roi_ativo(self):
        return self.modo_atual in self.MODOS_EDICAO

    def iniciar_selecao_led(self):
        self.base_selection_calls += 1
        if self._modo_edicao_roi_ativo():
            self.modo_atual = "tela_ao_vivo"
            self.view.atualizar_estado_selecao_led(False)
        else:
            self.modo_atual = "selecionar_leds_camera"
            self.view.atualizar_estado_selecao_led(True)

    def evento_clique_esquerdo(self, _evento=None):
        return "break"

    def _evento_arrastar_roi(self, _evento=None):
        return "break"

    def _evento_soltar_roi(self, _evento=None):
        return "break"

    def _evento_roda_roi(self, _evento=None):
        return "break"

    def _evento_apagar_roi(self, _evento=None):
        return "break"

    def _evento_cancelar_selecao_roi(self, _evento=None):
        return "break"

    def _evento_selecionar_todas_rois(self, _evento=None):
        return "break"

    def _evento_mover_roi_teclado(self, _evento=None):
        return "break"

    def capturar_frame_camera_para_analise(self, _evento=None):
        self.capture_calls += 1

    def parar_tela_ao_vivo(self, *_args, **_kwargs):
        self.stop_calls += 1
        self.camera_ativa = False
        self.modo_atual = "ocioso"

    def limpar_tela(self):
        self.clear_calls += 1
        self.modo_atual = "ocioso"


class FakeFullscreenApp(FullscreenLedSelectionMixin, FakeBaseApp):
    def _criar_interface_selecao_tela_cheia(self):
        self.fake_window = FakeWindow()
        self.fake_fullscreen_canvas = FakeCanvas("tela-cheia")
        return self.fake_window, self.fake_fullscreen_canvas


class FullscreenLedSelectionTests(unittest.TestCase):
    ASSINATURA = (
        ("LED_001", 900, 500, 18),
        ("LED_002", 1100, 520, 20),
    )

    def test_abrir_tela_cheia_nao_reinicia_nem_reconfigura_camera(self):
        app = FakeFullscreenApp()
        camera_original = app.camera_service
        configuracao_original = dict(app.configuracoes_camera)

        app.iniciar_selecao_led()

        self.assertEqual("selecionar_leds_camera", app.modo_atual)
        self.assertIs(app.camera_service, camera_original)
        self.assertEqual(configuracao_original, app.configuracoes_camera)
        self.assertEqual(0, camera_original.update_calls)
        self.assertEqual(0, camera_original.start_calls)
        self.assertEqual(0, camera_original.stop_calls)
        self.assertEqual(
            self.ASSINATURA,
            assinatura_geometria(app.leds_fixos_configurados),
        )
        self.assertIs(app.view.canvas, app.fake_fullscreen_canvas)
        self.assertTrue(app.fake_window.fullscreen)
        self.assertGreater(app.view.desenhos, 0)

    def test_canvas_tela_cheia_recebe_todos_eventos_do_editor(self):
        app = FakeFullscreenApp()
        app.iniciar_selecao_led()

        esperados = {
            "<Button-1>",
            "<Configure>",
            "<Motion>",
            "<Leave>",
            "<B1-Motion>",
            "<ButtonRelease-1>",
            "<MouseWheel>",
            "<Button-4>",
            "<Button-5>",
            "<Delete>",
            "<BackSpace>",
            "<Escape>",
            "<Control-a>",
            "<Control-A>",
            "<Left>",
            "<Right>",
            "<Up>",
            "<Down>",
            "<Return>",
            "<KP_Enter>",
        }
        self.assertTrue(
            esperados.issubset(set(app.fake_fullscreen_canvas.bindings))
        )

    def test_preview_usa_canvas_da_tela_cheia(self):
        app = FakeFullscreenApp()
        app.iniciar_selecao_led()

        callback = app.fake_fullscreen_canvas.bindings["<Motion>"]
        callback(FakeEvent(320, 240))

        self.assertTrue(app.view.preview_canvases)
        self.assertIs(
            app.fake_fullscreen_canvas,
            app.view.preview_canvases[-1],
        )

    def test_botao_ok_sai_do_modo_e_restaura_canvas_principal(self):
        app = FakeFullscreenApp()
        canvas_principal = app.view.canvas
        camera_original = app.camera_service
        app.iniciar_selecao_led()
        janela = app.fake_window

        app._confirmar_selecao_tela_cheia()

        self.assertEqual("tela_ao_vivo", app.modo_atual)
        self.assertFalse(app.view.selecao_led_ativa)
        self.assertIs(app.view.canvas, canvas_principal)
        self.assertTrue(janela.destroyed)
        self.assertIs(app.camera_service, camera_original)
        self.assertEqual(0, camera_original.update_calls)
        self.assertEqual(0, camera_original.start_calls)
        self.assertEqual(0, camera_original.stop_calls)
        self.assertEqual(
            self.ASSINATURA,
            assinatura_geometria(app.leds_fixos_configurados),
        )

    def test_cinquenta_aberturas_nao_produzem_deriva_de_mascara(self):
        app = FakeFullscreenApp()
        camera_original = app.camera_service

        for _ in range(50):
            app.iniciar_selecao_led()
            app._confirmar_selecao_tela_cheia()
            self.assertEqual(
                self.ASSINATURA,
                assinatura_geometria(app.leds_fixos_configurados),
            )
            self.assertEqual((1920, 1080, 20), (
                app.configuracoes_camera["width"],
                app.configuracoes_camera["height"],
                app.configuracoes_camera["fps"],
            ))

        self.assertEqual(0, camera_original.update_calls)
        self.assertEqual(0, camera_original.start_calls)
        self.assertEqual(0, camera_original.stop_calls)

    def test_parar_camera_fecha_tela_cheia_antes_do_fluxo_original(self):
        app = FakeFullscreenApp()
        canvas_principal = app.view.canvas
        app.iniciar_selecao_led()

        app.parar_tela_ao_vivo(manter_imagem=True)

        self.assertIs(app.view.canvas, canvas_principal)
        self.assertFalse(app._selecao_tela_cheia_esta_aberta())
        self.assertEqual(1, app.stop_calls)
        self.assertEqual("ocioso", app.modo_atual)


if __name__ == "__main__":
    unittest.main()
