from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import numpy as np

from src.platform.linux_f2_fixed_resolution import (
    LINUX_F2_FIXED_RESOLUTION,
    LinuxF2FixedResolutionMixin,
)
from src.platform.project_master_resolution_guard import ProjectMasterResolutionGuardMixin
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp


class _Service:
    def __init__(self) -> None:
        self.locked = None

    def definir_resolucao_travada(self, largura, altura):
        self.locked = (int(largura), int(altura))
        return self.locked


class _Base:
    def __init__(self) -> None:
        self.projeto_led_ativo = "PCI LED"
        self._resolucao_mestra_projeto_ativa = None
        self._resolucao_mestra_producao = None
        self.camera_service = _Service()
        self.camera_frame_atual = np.zeros((480, 640, 3), dtype=np.uint8)
        self.operacao_ativa = False
        self.apply_calls = []
        self.saved_master_calls = []
        self.sync_calls = 0
        self.prepare_calls = 0
        self.trigger_calls = 0
        self.open_calls = 0
        self.close_calls = 0
        self.error_calls = 0
        self.schedule_calls = []
        self.camera_config = None
        super().__init__()

    def _obter_resolucao_mestra_projeto(self, projeto=None):
        return (1920, 1080)

    def _salvar_resolucao_mestra_do_projeto_atual(self, projeto, resolucao):
        self.saved_master_calls.append((projeto, tuple(resolucao)))
        return True

    def obter_parametros_camera_dinamicos(self):
        return 1920, 1080, 20

    def _atualizar_config_camera_para_resolucao_mestra(self, resolucao):
        self.camera_config = tuple(resolucao)

    def _travar_servico_na_resolucao_mestra(self, service, resolucao):
        if service is not None:
            service.definir_resolucao_travada(*resolucao)

    def _aplicar_resolucao_mestra_projeto(self, projeto=None, reiniciar_se_necessario=True):
        self.apply_calls.append((projeto, bool(reiniciar_se_necessario)))
        self._resolucao_mestra_projeto_ativa = self._obter_resolucao_mestra_projeto(projeto)
        self._travar_servico_na_resolucao_mestra(
            self.camera_service,
            self._resolucao_mestra_projeto_ativa,
        )
        return False

    def _synchronize_masks_with_current_frame(self, force=False, schedule_operation_prepare=True):
        self.sync_calls += 1

    def abrir_tela_operacao(self):
        self.open_calls += 1
        self.operacao_ativa = True

    def fechar_tela_operacao(self):
        self.close_calls += 1
        self.operacao_ativa = False

    def preparar_tela_operacao(self):
        self.prepare_calls += 1

    def disparar_inspecao_operacao(self):
        self.trigger_calls += 1

    def _mostrar_erro_resolucao_mestra_producao(self):
        self.error_calls += 1

    def _agendar_preparo_operacao(self, atraso_ms):
        self.schedule_calls.append(int(atraso_ms))


class _App(LinuxF2FixedResolutionMixin, _Base):
    pass


class LinuxF2FixedResolutionTests(unittest.TestCase):
    def test_constante_operacional_linux_e_640x480(self):
        self.assertEqual((640, 480), LINUX_F2_FIXED_RESOLUTION)

    def test_projeto_led_linux_ignora_master_antiga_e_usa_640x480(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            self.assertEqual((640, 480), app._obter_resolucao_mestra_projeto("PCI LED"))
            self.assertEqual((640, 480, 20), app.obter_parametros_camera_dinamicos())

    def test_windows_preserva_master_e_parametros_existentes(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "win32"):
            app = _App()
            self.assertEqual((1920, 1080), app._obter_resolucao_mestra_projeto("PCI LED"))
            self.assertEqual((1920, 1080, 20), app.obter_parametros_camera_dinamicos())

    def test_salvar_master_no_linux_persiste_640x480_mesmo_se_receber_1080p(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            self.assertTrue(
                app._salvar_resolucao_mestra_do_projeto_atual(
                    "PCI LED",
                    (1920, 1080),
                )
            )
            self.assertEqual([("PCI LED", (640, 480))], app.saved_master_calls)

    def test_abrir_f2_linux_ativa_trava_antes_da_operacao(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.camera_frame_atual = np.zeros((1080, 1920, 3), dtype=np.uint8)

            app.abrir_tela_operacao()

            self.assertTrue(app._linux_f2_resolution_lock_active)
            self.assertTrue(app.operacao_ativa)
            self.assertEqual((640, 480), app._resolucao_mestra_producao)
            self.assertEqual((640, 480), app._resolucao_mestra_projeto_ativa)
            self.assertEqual((640, 480), app.camera_service.locked)
            self.assertEqual((640, 480), app.camera_config)
            self.assertEqual(1, app.open_calls)
            self.assertEqual(1, len(app.apply_calls))

    def test_durante_f2_linux_sincronizador_nao_pode_recalcular_roi(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = True
            app._linux_f2_resolution_lock_active = True
            app._synchronize_masks_with_current_frame(force=True)
            self.assertEqual(0, app.sync_calls)

    def test_fora_do_f2_sincronizador_continua_existindo(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = False
            app._synchronize_masks_with_current_frame(force=True)
            self.assertEqual(1, app.sync_calls)

    def test_frame_1920x1080_e_rejeitado_antes_de_preparar_f2(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = True
            app._linux_f2_resolution_lock_active = True
            app.camera_frame_atual = np.zeros((1080, 1920, 3), dtype=np.uint8)

            app.preparar_tela_operacao()

            self.assertEqual(0, app.prepare_calls)
            self.assertEqual(1, app.error_calls)
            self.assertEqual([150], app.schedule_calls)
            self.assertEqual((640, 480), app.camera_service.locked)

    def test_frame_1280x720_e_rejeitado_antes_do_trigger(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = True
            app._linux_f2_resolution_lock_active = True
            app.camera_frame_atual = np.zeros((720, 1280, 3), dtype=np.uint8)

            app.disparar_inspecao_operacao()

            self.assertEqual(0, app.trigger_calls)
            self.assertEqual(1, app.error_calls)
            self.assertEqual((640, 480), app.camera_service.locked)

    def test_frame_640x480_pode_preparar_e_analisar_normalmente(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = True
            app._linux_f2_resolution_lock_active = True
            app.camera_frame_atual = np.zeros((480, 640, 3), dtype=np.uint8)

            app.preparar_tela_operacao()
            app.disparar_inspecao_operacao()

            self.assertEqual(1, app.prepare_calls)
            self.assertEqual(1, app.trigger_calls)
            self.assertEqual(0, app.error_calls)

    def test_fechar_f2_libera_flag_sem_mudar_resolucao_do_servico(self):
        with patch("src.platform.linux_f2_fixed_resolution.sys.platform", "linux"):
            app = _App()
            app.operacao_ativa = True
            app._linux_f2_resolution_lock_active = True
            app.camera_service.definir_resolucao_travada(640, 480)

            app.fechar_tela_operacao()

            self.assertFalse(app._linux_f2_resolution_lock_active)
            self.assertFalse(app.operacao_ativa)
            self.assertEqual((640, 480), app.camera_service.locked)
            self.assertEqual(1, app.close_calls)

    def test_mixin_fica_antes_do_guard_de_resolucao_mestra_no_app_final(self):
        mro = RaspberryPi3ProductionApp.__mro__
        self.assertLess(
            mro.index(LinuxF2FixedResolutionMixin),
            mro.index(ProjectMasterResolutionGuardMixin),
        )

    def test_barreira_nao_importa_nem_controla_display_f3(self):
        fonte = inspect.getsource(__import__(
            "src.platform.linux_f2_fixed_resolution",
            fromlist=["LinuxF2FixedResolutionMixin"],
        ))
        self.assertNotIn("DisplayProjectRepository", fonte)
        self.assertNotIn("DisplayProductionF3Mixin", fonte)
        self.assertNotIn("display_project", fonte)


if __name__ == "__main__":
    unittest.main()
