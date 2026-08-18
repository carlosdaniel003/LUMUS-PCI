import json
import tempfile
import unittest
from pathlib import Path

from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection
from src.platform.fixed_mask_geometry_guard import (
    FixedMaskGeometryGuardMixin,
    assinatura_geometria,
    copiar_mascara_absoluta,
    instalar_repositorio_mascaras_absolutas,
)
from src.platform.led_mask_resolution_sync import ResolutionSynchronizedLedMasksMixin
from src.platform.led_project_repository import instalar_repositorio_projetos_led
from src.platform.mask_resolution_legacy_reference import (
    instalar_referencia_resolucao_mascaras_legadas,
)


class FakeFrame:
    def __init__(self, largura: int, altura: int):
        self.shape = (altura, largura, 3)
        self.size = largura * altura * 3


class FakeRepository:
    def __init__(self):
        self.active = "PLACA A"
        self.active_reads = 0
        self.projects = {
            "PLACA A": [
                LedSelection(
                    "LED_001",
                    160,
                    120,
                    20,
                ).com_normalizacao(640, 480),
                LedSelection(
                    "SEG_001",
                    480,
                    360,
                    1,
                    tipo_roi="segmento",
                    largura=100,
                    altura=24,
                    angulo=12.0,
                ).com_normalizacao(640, 480),
            ],
            "PLACA B": [
                LedSelection("LED_101", 320, 240, 14).com_normalizacao(640, 480),
            ],
        }

    def obter_projeto_led_ativo(self):
        self.active_reads += 1
        return self.active

    def carregar_leds_fixos(self, projeto=None):
        nome = projeto or self.active
        return [copiar_mascara_absoluta(led) for led in self.projects[nome]]

    def salvar_leds_fixos(self, leds, projeto=None, **_kwargs):
        nome = projeto or self.active
        self.projects[nome] = [copiar_mascara_absoluta(led) for led in leds]
        return {}


class FakeOperationWindow:
    def __init__(self):
        self.previews = []

    def update_preview(self, _frame, leds):
        self.previews.append(assinatura_geometria(leds))


class FakeEngine:
    def __init__(self):
        self._frame_width = 640
        self._frame_height = 480
        self.invalidated = 0

    def invalidate(self):
        self.invalidated += 1
        self._frame_width = 0
        self._frame_height = 0


class FakeRoot:
    def after_cancel(self, _id):
        return None


class FakeView:
    def desenhar_canvas(self, _leds, _resultados):
        return None


class FakeBaseApp:
    def __init__(self):
        self.config_repository = FakeRepository()
        self.modo_atual = "ocioso"
        self.guias_leds_fixos_visiveis = True
        self.selecao_manual_camera_ativa = False
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()
        self.leds_selecionados = []
        self.leds_manuais_camera = []
        self.operacao_leds_preview = []
        self.resultados_led_atual = []
        self.camera_frame_atual = FakeFrame(640, 480)
        self.imagem_original = self.camera_frame_atual
        self.largura_original = 640
        self.altura_original = 480
        self.operacao_ativa = False
        self.operacao_processando = False
        self.operacao_window = FakeOperationWindow()
        self.operacao_engine = FakeEngine()
        self._operacao_preparo_after_id = None
        self.root = FakeRoot()
        self.view = FakeView()
        self.scheduled = []
        self.frame_updates = 0
        self.production_prepares = 0
        self.production_triggers = 0
        self.production_opens = 0

    def _agendar_preparo_operacao(self, delay):
        self.scheduled.append(delay)

    def atualizar_frame_camera(self):
        self.frame_updates += 1

    def salvar_leds_fixos(self):
        self.leds_fixos_configurados = [
            copiar_mascara_absoluta(led)
            for led in self.leds_selecionados
        ]
        self.config_repository.salvar_leds_fixos(self.leds_fixos_configurados)

    def carregar_leds_fixos(self):
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()

    def carregar_configuracao(self):
        self.carregar_leds_fixos()

    def salvar_configuracoes_sistema(self, *_args, **_kwargs):
        return None

    def abrir_tela_operacao(self):
        self.production_opens += 1

    def preparar_tela_operacao(self):
        self.production_prepares += 1

    def disparar_inspecao_operacao(self):
        self.production_triggers += 1

    def selecionar_led_para_analise(self, _x, _y):
        return None


class LegacyBaseApp(FakeBaseApp):
    def __init__(self):
        super().__init__()
        self.configuracoes_camera = {
            "resolution_mode": "full_hd",
            "width": 1920,
            "height": 1080,
        }
        self.config_repository.projects["PLACA A"] = [
            LedSelection("LED_LEGADO", 960, 540, 30)
        ]
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()
        self.camera_frame_atual = FakeFrame(640, 480)
        self.imagem_original = self.camera_frame_atual
        self.largura_original = 640
        self.altura_original = 480


class GuardedFakeApp(
    FixedMaskGeometryGuardMixin,
    ResolutionSynchronizedLedMasksMixin,
    FakeBaseApp,
):
    pass


class GuardedLegacyApp(
    FixedMaskGeometryGuardMixin,
    ResolutionSynchronizedLedMasksMixin,
    LegacyBaseApp,
):
    pass


class FixedMaskGeometryGuardTests(unittest.TestCase):
    def test_copia_preserva_base_normalizada(self):
        origem = LedSelection(
            "LED_001",
            160,
            120,
            20,
        ).com_normalizacao(640, 480)

        copia = copiar_mascara_absoluta(origem)

        self.assertEqual((160, 120, 20), (copia.centro_x, copia.centro_y, copia.raio))
        self.assertTrue(copia.possui_coordenadas_normalizadas())
        self.assertEqual((640, 480), (copia.largura_base, copia.altura_base))
        self.assertAlmostEqual(0.25, copia.centro_x_normalizado)
        self.assertAlmostEqual(0.25, copia.centro_y_normalizado)

    def test_640x480_para_1920x1080_acompanha_posicao_relativa(self):
        app = GuardedFakeApp()
        app._mask_resolution_active = (640, 480)

        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.imagem_original = app.camera_frame_atual
        app._synchronize_masks_with_current_frame(force=True)

        led = app.leds_fixos_configurados[0]
        self.assertEqual((480, 270), (led.centro_x, led.centro_y))
        self.assertAlmostEqual(0.25, led.centro_x / 1920.0, places=6)
        self.assertAlmostEqual(0.25, led.centro_y / 1080.0, places=6)
        self.assertTrue(led.possui_coordenadas_normalizadas())

        segmento = app.leds_fixos_configurados[1]
        self.assertEqual((1440, 810), (segmento.centro_x, segmento.centro_y))
        self.assertEqual(300, segmento.largura)
        self.assertEqual(54, segmento.altura)
        self.assertAlmostEqual(12.0, segmento.angulo)

    def test_mascara_volta_exatamente_apos_mudanca_de_resolucao(self):
        app = GuardedFakeApp()
        app._mask_resolution_active = (640, 480)
        assinatura_inicial = assinatura_geometria(app.leds_fixos_configurados)

        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.imagem_original = app.camera_frame_atual
        app._synchronize_masks_with_current_frame(force=True)

        app.camera_frame_atual = FakeFrame(640, 480)
        app.imagem_original = app.camera_frame_atual
        app._synchronize_masks_with_current_frame(force=True)

        self.assertEqual(
            assinatura_inicial,
            assinatura_geometria(app.leds_fixos_configurados),
        )

    def test_500_trocas_de_resolucao_nao_acumulam_deriva(self):
        app = GuardedFakeApp()
        app._mask_resolution_active = (640, 480)
        assinatura_inicial = assinatura_geometria(app.leds_fixos_configurados)

        for indice in range(500):
            largura, altura = (
                (1920, 1080)
                if indice % 2 == 0
                else (640, 480)
            )
            app.camera_frame_atual = FakeFrame(largura, altura)
            app.imagem_original = app.camera_frame_atual
            app._synchronize_masks_with_current_frame(force=True)

        self.assertEqual(
            assinatura_inicial,
            assinatura_geometria(app.leds_fixos_configurados),
        )
        for led in app.leds_fixos_configurados:
            self.assertTrue(led.possui_coordenadas_normalizadas())

    def test_mascara_legada_usa_perfil_configurado_antes_do_primeiro_frame(self):
        instalar_referencia_resolucao_mascaras_legadas()
        app = GuardedLegacyApp()

        self.assertEqual(1, len(app.leds_fixos_configurados))
        exibida = app.leds_fixos_configurados[0]
        canonical = app._mask_guard_snapshot[0]

        self.assertEqual((320, 240, 10), (
            exibida.centro_x,
            exibida.centro_y,
            exibida.raio,
        ))
        self.assertTrue(canonical.possui_coordenadas_normalizadas())
        self.assertEqual((1920, 1080), (
            canonical.largura_base,
            canonical.altura_base,
        ))
        self.assertAlmostEqual(0.5, canonical.centro_x_normalizado)
        self.assertAlmostEqual(0.5, canonical.centro_y_normalizado)

    def test_mutacao_fora_do_editor_e_restaurada_na_resolucao_atual(self):
        app = GuardedFakeApp()
        app._mask_resolution_active = (640, 480)
        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.imagem_original = app.camera_frame_atual
        app._synchronize_masks_with_current_frame(force=True)

        app.leds_fixos_configurados[0].centro_x += 73
        app.leds_fixos_configurados[1].centro_y -= 41
        app._mask_guard_enforce()

        self.assertEqual((480, 270), (
            app.leds_fixos_configurados[0].centro_x,
            app.leds_fixos_configurados[0].centro_y,
        ))
        self.assertEqual((1440, 810), (
            app.leds_fixos_configurados[1].centro_x,
            app.leds_fixos_configurados[1].centro_y,
        ))
        self.assertGreaterEqual(app._mask_guard_corrections, 1)

    def test_troca_de_projeto_adapta_novo_projeto_a_resolucao_corrente(self):
        app = GuardedFakeApp()
        app._mask_resolution_active = (640, 480)
        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.imagem_original = app.camera_frame_atual
        app.config_repository.active = "PLACA B"

        app.preparar_tela_operacao()

        self.assertEqual(1, len(app.leds_fixos_configurados))
        led = app.leds_fixos_configurados[0]
        self.assertEqual((960, 540), (led.centro_x, led.centro_y))
        self.assertTrue(led.possui_coordenadas_normalizadas())

    def test_preview_operacao_recebe_geometria_da_resolucao_atual(self):
        app = GuardedFakeApp()
        app.operacao_ativa = True
        app._mask_resolution_active = (640, 480)
        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.imagem_original = app.camera_frame_atual

        app._synchronize_masks_with_current_frame(force=True)

        self.assertTrue(app.operacao_window.previews)
        preview = app.operacao_window.previews[-1]
        self.assertEqual(("LED_001", 480, 270, 60), preview[0])

    def test_repositorio_persiste_normalizacao_e_resolucao_base(self):
        instalar_repositorio_projetos_led()
        instalar_repositorio_mascaras_absolutas()

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "config.json"
            repository = ConfigRepository(config_file=caminho)
            repository.salvar_leds_fixos(
                [LedSelection("LED_001", 160, 120, 20)],
                largura_base=640,
                altura_base=480,
                projeto="PLACA TESTE",
            )

            dados = json.loads(caminho.read_text(encoding="utf-8"))
            salvo = dados["led_projects"]["PLACA TESTE"]["fixed_leds"][0]
            carregado = repository.carregar_leds_fixos("PLACA TESTE")[0]

        self.assertEqual(
            {"width": 640, "height": 480},
            salvo["base_resolution"],
        )
        self.assertAlmostEqual(0.25, salvo["normalized"]["x"])
        self.assertAlmostEqual(0.25, salvo["normalized"]["y"])
        self.assertTrue(carregado.possui_coordenadas_normalizadas())
        self.assertEqual((640, 480), (
            carregado.largura_base,
            carregado.altura_base,
        ))


if __name__ == "__main__":
    unittest.main()
