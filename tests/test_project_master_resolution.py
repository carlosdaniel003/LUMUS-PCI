import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection
from src.platform.led_project_repository import (
    instalar_repositorio_projetos_led,
)
from src.platform.linux_camera_compatibility import (
    LinuxCameraCompatibilityMixin,
)
from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)
from src.platform.project_master_resolution import (
    ProjectMasterResolutionMixin,
)
from src.platform.windows_camera_compatibility import (
    WindowsCameraCompatibilityMixin,
)


class FakeRepository:
    def __init__(self, master=(640, 480)):
        self.active = "PLACA A"
        self.master = {"PLACA A": master}
        self.set_calls = []

    def obter_resolucao_mestra_projeto_led(self, projeto=None):
        return self.master.get(projeto or self.active)

    def definir_resolucao_mestra_projeto_led(self, projeto, largura, altura):
        resolucao = (int(largura), int(altura))
        self.master[projeto] = resolucao
        self.set_calls.append((projeto, *resolucao))
        return True

    def obter_projeto_led_ativo(self):
        return self.active


class FakeCameraService:
    def __init__(self, resolucao=(640, 480), solicitada=None, indice=1):
        self.resolucao = resolucao
        self.solicitada = solicitada or resolucao
        self.indice_camera = indice
        self.lock_calls = []

    def obter_snapshot(self):
        return SimpleNamespace(
            resolucao=self.resolucao,
            resolucao_solicitada=self.solicitada,
        )

    def definir_resolucao_travada(self, largura, altura):
        self.lock_calls.append((int(largura), int(altura)))
        self.solicitada = (int(largura), int(altura))


class FakeOperationWindow:
    def __init__(self):
        self.errors = []
        self.preview_status = []

    def show_error(self, mensagem, **kwargs):
        self.errors.append((mensagem, kwargs))

    def set_preview_status(self, mensagem, cor):
        self.preview_status.append((mensagem, cor))


class FakeEngine:
    def __init__(self):
        self.invalidations = 0

    def invalidate(self):
        self.invalidations += 1


class FakeView:
    def __init__(self):
        self.status = []

    def atualizar_status(self, texto):
        self.status.append(texto)


class FakeBase:
    def __init__(self, master=(640, 480), atual=(640, 480)):
        self.config_repository = FakeRepository(master)
        self.projeto_led_ativo = "PLACA A"
        self.configuracoes_camera = {
            "resolution_mode": "custom",
            "width": atual[0],
            "height": atual[1],
            "fps_mode": "manual",
            "fps": 20,
            "format": "MJPG",
        }
        self.camera_service = FakeCameraService(atual)
        self.camera_ativa = True
        self.camera_frame_atual = np.zeros(
            (atual[1], atual[0], 3),
            dtype=np.uint8,
        )
        self.imagem_original = self.camera_frame_atual
        self.largura_original = atual[0]
        self.altura_original = atual[1]
        self.indice_camera_selecionada = 1
        self.operacao_ativa = False
        self.operacao_total = 0
        self.operacao_ok = 0
        self.operacao_ng = 0
        self.operacao_window = FakeOperationWindow()
        self.operacao_engine = FakeEngine()
        self.view = FakeView()
        self.stop_calls = 0
        self.start_calls = 0
        self.open_operation_calls = 0
        self.prepare_calls = 0
        self.trigger_calls = 0
        self.sync_calls = 0
        self.save_calls = 0
        self.load_selection = None

    def obter_parametros_camera_dinamicos(self):
        return 1920, 1080, 20

    def parar_tela_ao_vivo(self, manter_imagem=True):
        del manter_imagem
        self.stop_calls += 1
        self.camera_ativa = False
        self.camera_service = None

    def iniciar_tela_ao_vivo(self):
        self.start_calls += 1
        largura = int(self.configuracoes_camera["width"])
        altura = int(self.configuracoes_camera["height"])
        self.camera_service = FakeCameraService((largura, altura))
        self.camera_ativa = True
        self.camera_frame_atual = np.zeros(
            (altura, largura, 3),
            dtype=np.uint8,
        )

    def abrir_tela_operacao(self):
        self.open_operation_calls += 1
        self.operacao_ativa = True

    def preparar_tela_operacao(self):
        self.prepare_calls += 1

    def disparar_inspecao_operacao(self):
        self.trigger_calls += 1

    def _synchronize_masks_with_current_frame(self, **_kwargs):
        self.sync_calls += 1

    def _salvar_leds_no_projeto(self, nome_projeto, **_kwargs):
        del nome_projeto
        self.save_calls += 1
        return True

    def carregar_leds_fixos(self):
        self._ultimo_projeto_escolhido_carregar_leds = self.load_selection


class FakeApp(ProjectMasterResolutionMixin, FakeBase):
    pass


class _LinuxBase:
    def __init__(self):
        self._indice_camera_solicitado = 0
        self._indice_camera_ativo = 0
        self.fps = 20
        self._resolucao_mestra_travada = (640, 480)


class _LinuxServiceFake(LinuxCameraCompatibilityMixin, _LinuxBase):
    pass


class _WindowsBase:
    ESTADO_DESCONECTADA = "desconectada"

    def __init__(self):
        self.largura = 640
        self.altura = 480
        self.fps = 20
        self.formato_camera = "MJPG"
        self.perfil_automatico = False
        self._resolucao_solicitada = (640, 480)
        self._fps_solicitado = 20
        self._formato_solicitado = "MJPG"
        self._resolucao_mestra_travada = (640, 480)
        self.calls = []

    def _abrir_camera(self):
        self.calls.append(self.perfil_automatico)
        return False

    def _definir_estado(self, *_args):
        return None

    def obter_diagnostico_fluxo(self):
        return {}


class _WindowsServiceFake(WindowsCameraCompatibilityMixin, _WindowsBase):
    pass


class ProjectMasterResolutionTests(unittest.TestCase):
    def test_repositorio_persiste_resolucao_mestra_ao_salvar_leds(self):
        instalar_repositorio_projetos_led()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "config.json"
            repo = ConfigRepository(config_file=caminho)
            self.assertTrue(repo.adicionar_projeto_led("PLACA TESTE"))
            repo.salvar_leds_fixos(
                [LedSelection("LED_001", 160, 120, 20)],
                largura_base=640,
                altura_base=480,
                projeto="PLACA TESTE",
            )

            self.assertEqual(
                (640, 480),
                repo.obter_resolucao_mestra_projeto_led("PLACA TESTE"),
            )
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            projeto = dados["led_projects"]["PLACA TESTE"]
            self.assertEqual(
                {"width": 640, "height": 480},
                projeto["master_resolution"],
            )
            self.assertEqual(
                {"width": 640, "height": 480},
                projeto["fixed_leds"][0]["base_resolution"],
            )

    def test_definir_mestre_manual_nao_apaga_leds(self):
        instalar_repositorio_projetos_led()
        with tempfile.TemporaryDirectory() as pasta:
            repo = ConfigRepository(config_file=Path(pasta) / "config.json")
            repo.adicionar_projeto_led("PLACA TESTE")
            repo.salvar_leds_fixos(
                [LedSelection("LED_001", 100, 80, 10)],
                largura_base=640,
                altura_base=480,
                projeto="PLACA TESTE",
            )
            self.assertTrue(
                repo.definir_resolucao_mestra_projeto_led(
                    "PLACA TESTE",
                    1920,
                    1080,
                )
            )
            self.assertEqual(
                1,
                len(repo.carregar_leds_fixos("PLACA TESTE")),
            )
            self.assertEqual(
                (1920, 1080),
                repo.obter_resolucao_mestra_projeto_led("PLACA TESTE"),
            )

    def test_mesma_resolucao_nao_para_nem_reinicia_camera(self):
        app = FakeApp(master=(640, 480), atual=(640, 480))
        service = app.camera_service

        reiniciou = app._aplicar_resolucao_mestra_projeto("PLACA A")

        self.assertFalse(reiniciou)
        self.assertEqual(0, app.stop_calls)
        self.assertEqual(0, app.start_calls)
        self.assertEqual([(640, 480)], service.lock_calls)

    def test_resolucao_diferente_reinicia_exatamente_uma_vez(self):
        app = FakeApp(master=(640, 480), atual=(1920, 1080))

        reiniciou = app._aplicar_resolucao_mestra_projeto("PLACA A")

        self.assertTrue(reiniciou)
        self.assertEqual(1, app.stop_calls)
        self.assertEqual(1, app.start_calls)
        self.assertEqual((640, 480), app._obter_resolucao_camera_real())
        self.assertEqual(1, app.indice_camera_selecionada)

    def test_salvar_projeto_grava_resolucao_real_atual_como_mestre(self):
        app = FakeApp(master=(1920, 1080), atual=(640, 480))

        self.assertTrue(app._salvar_leds_no_projeto("PLACA A"))

        self.assertEqual(1, app.save_calls)
        self.assertEqual(
            [("PLACA A", 640, 480)],
            app.config_repository.set_calls,
        )
        self.assertEqual((640, 480), app._resolucao_mestra_projeto_ativa)

    def test_cancelar_carregar_leds_nao_troca_resolucao(self):
        app = FakeApp(master=(640, 480), atual=(1920, 1080))
        app.load_selection = None

        app.carregar_leds_fixos()

        self.assertEqual(0, app.stop_calls)
        self.assertEqual(0, app.start_calls)

    def test_carregar_projeto_aplica_resolucao_mestra(self):
        app = FakeApp(master=(640, 480), atual=(1920, 1080))
        app.load_selection = "PLACA A"

        app.carregar_leds_fixos()

        self.assertEqual(1, app.stop_calls)
        self.assertEqual(1, app.start_calls)
        self.assertEqual((640, 480), app._obter_resolucao_camera_real())

    def test_f2_bloqueia_preparo_analise_e_sync_se_frame_mudar(self):
        app = FakeApp(master=(640, 480), atual=(640, 480))
        app.operacao_ativa = True
        app._resolucao_mestra_producao = (640, 480)
        app.camera_frame_atual = np.zeros((1080, 1920, 3), dtype=np.uint8)

        app.preparar_tela_operacao()
        app.disparar_inspecao_operacao()
        app._synchronize_masks_with_current_frame(force=True)

        self.assertEqual(0, app.prepare_calls)
        self.assertEqual(0, app.trigger_calls)
        self.assertEqual(0, app.sync_calls)
        self.assertGreaterEqual(app.operacao_engine.invalidations, 2)
        self.assertTrue(app.operacao_window.errors)

    def test_servico_descarta_frame_que_viola_resolucao_travada(self):
        service = LiveFixedFullHdCameraService.__new__(
            LiveFixedFullHdCameraService
        )
        service._lock = threading.RLock()
        service._resolucao_mestra_travada = (640, 480)
        service._resolution_mismatch_count = 0
        service._ultimo_motivo_descarte = ""
        service.RESOLUTION_MISMATCH_BEFORE_SWITCH = 3

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        LiveFixedFullHdCameraService._publicar_frame_otimizado(
            service,
            frame,
            estavel=True,
        )

        self.assertEqual(1, service._resolution_mismatch_count)
        self.assertIn("Frame descartado", service._ultimo_motivo_descarte)
        self.assertIn("640x480", service._ultimo_motivo_descarte)

    def test_linux_com_trava_gera_somente_candidatos_da_resolucao_mestra(self):
        service = _LinuxServiceFake()
        with patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ), patch(
            "src.platform.linux_camera_compatibility.descobrir_dispositivos_video",
            return_value=(("/dev/video0", 0),),
        ), patch(
            "src.platform.linux_camera_compatibility.opencv_tem_gstreamer",
            return_value=False,
        ):
            candidatos = service._candidatos_linux()

        self.assertTrue(candidatos)
        self.assertTrue(all(c.tipo != "auto" for c in candidatos))
        self.assertTrue(
            all((c.largura, c.altura) == (640, 480) for c in candidatos)
        )

    def test_windows_com_trava_nao_cai_para_auto(self):
        service = _WindowsServiceFake()
        with patch(
            "src.platform.windows_camera_compatibility.sys.platform",
            "win32",
        ):
            self.assertFalse(service._abrir_camera())

        self.assertEqual([False], service.calls)
        self.assertFalse(service._windows_fallback_automatico_ativo)

    def test_codigo_da_interface_expoe_opcao_resolucao_mestra(self):
        import inspect

        fonte = inspect.getsource(ProjectMasterResolutionMixin)
        self.assertIn("Resolução mestre", fonte)
        self.assertIn("Gerenciar configurações de LEDs", fonte)
        self.assertIn("_instalar_botao_resolucao_mestra_carregar_leds", fonte)


if __name__ == "__main__":
    unittest.main()
