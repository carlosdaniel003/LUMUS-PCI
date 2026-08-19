import unittest
from types import SimpleNamespace

from src.platform.neutral_project_startup import NeutralProjectStartupMixin
from src.platform.project_master_resolution import ProjectMasterResolutionMixin
from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)


class FakeRepository:
    def __init__(self):
        self.active = "DISPLAY_7"
        self.master = {"DISPLAY_7": (1600, 500)}

    def obter_resolucao_mestra_projeto_led(self, projeto=None):
        nome = projeto or self.active
        return self.master.get(nome)

    def obter_projeto_led_ativo(self):
        return self.active


class FakeView:
    def __init__(self):
        self.label_meta_placa = SimpleNamespace(configure=self._configure)
        self.placa = "DISPLAY_7"

    def _configure(self, **kwargs):
        if "text" in kwargs:
            self.placa = kwargs["text"]


class FakeBase:
    def __init__(self):
        self.config_repository = FakeRepository()
        self.projeto_led_ativo = "DISPLAY_7"
        self.leds_fixos_configurados = ["ROI_ANTIGA"]
        self.leds_selecionados = ["ROI_ANTIGA"]
        self.resultados_led_atual = ["NG_ANTIGO"]
        self._referencias_ativas_por_tipo = {
            "aceso": ["REF_ON"],
            "apagado": ["REF_OFF"],
            "pouca_luz": ["REF_LOW"],
        }
        self.features_referencia_acesa = "REF_ON"
        self.features_referencia_apagada = "REF_OFF"
        self.features_referencia_pouca_luz = "REF_LOW"
        self.referencias_acesas_ativas = ["REF_ON"]
        self.referencias_apagadas_ativas = ["REF_OFF"]
        self.referencias_pouca_luz_ativas = ["REF_LOW"]
        self.configuracoes_camera = {
            "resolution_mode": "full_hd",
            "width": 1920,
            "height": 1080,
            "fps_mode": "manual",
            "fps": 20,
            "format": "MJPG",
        }
        self.camera_service = None
        self.camera_ativa = False
        self.view = FakeView()
        self.painel_updates = 0
        self.start_calls = 0

    def atualizar_painel_inicial(self):
        self.painel_updates += 1

    def obter_parametros_camera_dinamicos(self):
        return 1920, 1080, 20

    def iniciar_tela_ao_vivo(self):
        self.start_calls += 1
        # Reproduz o comportamento legado do ODINApp que recarrega o espelho
        # fixed_leds do último projeto ao iniciar a câmera.
        self.leds_fixos_configurados = ["ROI_ANTIGA"]

    def _aplicar_resolucao_mestra_projeto(
        self,
        projeto=None,
        reiniciar_se_necessario=True,
    ):
        del projeto, reiniciar_se_necessario
        return False


class FakeApp(
    NeutralProjectStartupMixin,
    ProjectMasterResolutionMixin,
    FakeBase,
):
    pass


class NeutralProjectStartupTests(unittest.TestCase):
    def test_inicio_ignora_ultimo_projeto_persistido(self):
        app = FakeApp()

        self.assertEqual("", app._projeto_led_sessao_carregado)
        self.assertEqual("", app.projeto_led_ativo)
        self.assertIsNone(app._resolucao_mestra_projeto_ativa)
        self.assertEqual([], app.leds_fixos_configurados)
        self.assertEqual([], app.leds_selecionados)
        self.assertEqual([], app.resultados_led_atual)
        self.assertEqual("MANUAL", app.view.placa)

    def test_inicio_nao_herda_referencias_do_projeto_anterior(self):
        app = FakeApp()

        self.assertEqual([], app._referencias_ativas_por_tipo["aceso"])
        self.assertEqual([], app._referencias_ativas_por_tipo["apagado"])
        self.assertEqual([], app._referencias_ativas_por_tipo["pouca_luz"])
        self.assertIsNone(app.features_referencia_acesa)
        self.assertIsNone(app.features_referencia_apagada)
        self.assertIsNone(app.features_referencia_pouca_luz)
        self.assertEqual("", app._projeto_referencia_ativo())

    def test_sem_projeto_parametros_da_camera_nao_usam_master_1600x500(self):
        app = FakeApp()

        self.assertEqual(
            (1920, 1080, 20),
            app.obter_parametros_camera_dinamicos(),
        )
        self.assertIsNone(app._atualizar_resolucao_mestra_projeto_ativa())

    def test_iniciar_camera_sem_projeto_remove_fixed_leds_herdados(self):
        app = FakeApp()

        app.iniciar_tela_ao_vivo()

        self.assertEqual(1, app.start_calls)
        self.assertEqual([], app.leds_fixos_configurados)
        self.assertIsNone(app._resolucao_mestra_projeto_ativa)

    def test_projeto_so_passa_a_controlar_resolucao_apos_acao_explicita(self):
        app = FakeApp()
        self.assertIsNone(app._atualizar_resolucao_mestra_projeto_ativa())

        app._projeto_led_sessao_carregado = "DISPLAY_7"
        app.projeto_led_ativo = "DISPLAY_7"

        self.assertEqual(
            (1600, 500),
            app._atualizar_resolucao_mestra_projeto_ativa(),
        )

    def test_windows_sem_master_preserva_full_hd_geral_com_fallback_existente(self):
        configuracoes = LiveFixedFullHdCameraService._windows_native_settings(
            {
                "resolution_mode": "full_hd",
                "width": 1920,
                "height": 1080,
                "fps_mode": "manual",
                "fps": 20,
                "format": "MJPG",
            }
        )
        self.assertEqual("full_hd", configuracoes["resolution_mode"])
        self.assertEqual(1920, configuracoes["width"])
        self.assertEqual(1080, configuracoes["height"])
        self.assertEqual(20, configuracoes["fps"])
        self.assertEqual("MJPG", configuracoes["format"])


if __name__ == "__main__":
    unittest.main()
