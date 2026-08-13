import inspect
import unittest

from src.platform.camera_live_settings import CameraLiveSettingsMixin
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp
from src.ui.main_window_parts.settings.abrir_janela_configuracoes_ao_vivo import (
    LIVE_CAMERA_DEBOUNCE_MS,
    construir_configuracoes_camera_ao_vivo,
)


class _VarFake:
    def __init__(self, valor):
        self.valor = valor

    def get(self):
        return self.valor


class _RepositoryFake:
    def normalizar_configuracoes_camera(self, configuracoes):
        return dict(configuracoes or {})


class _CameraServiceFake:
    ESTADO_CONECTADA = "conectada"

    def __init__(self):
        self.atualizacoes = []
        self.paradas = 0
        self.inicios = 0

    def atualizar_configuracoes_camera(self, configuracoes):
        self.atualizacoes.append(dict(configuracoes))

    def obter_status_controles_camera(self):
        return {
            "focus": {
                "status": "aplicado",
                "valor_solicitado": 137.0,
                "valor_lido": 137.0,
            }
        }

    def parar(self):
        self.paradas += 1

    def iniciar(self):
        self.inicios += 1


class CameraLiveSettingsTests(unittest.TestCase):
    def test_perfil_final_inclui_mixin_camera_ao_vivo(self):
        self.assertIn(CameraLiveSettingsMixin, RaspberryPi3ProductionApp.__mro__)

    def test_foco_manual_e_montado_imediatamente(self):
        base = {
            "focus_auto": True,
            "focus_enabled": False,
            "focus": 0.0,
            "rotation": 0,
        }
        variaveis = {
            "focus_auto": _VarFake(False),
            "focus_enabled": _VarFake(True),
            "focus": _VarFake(137),
            "_rotation_label": _VarFake("90°"),
        }
        configuracoes = construir_configuracoes_camera_ao_vivo(
            base,
            variaveis,
        )
        self.assertFalse(configuracoes["focus_auto"])
        self.assertTrue(configuracoes["focus_enabled"])
        self.assertEqual(137.0, configuracoes["focus"])
        self.assertEqual(90, configuracoes["rotation"])

    def test_controles_basicos_e_avancados_sao_preservados(self):
        base = {
            "pan_enabled": False,
            "pan": 0,
            "brightness_enabled": False,
            "brightness": 128,
            "white_balance_auto": True,
        }
        variaveis = {
            "pan_enabled": _VarFake(True),
            "pan": _VarFake(24),
            "brightness_enabled": _VarFake(True),
            "brightness": _VarFake(170),
            "white_balance_auto": _VarFake(False),
            "white_balance_enabled": _VarFake(True),
            "white_balance": _VarFake(5100),
        }
        configuracoes = construir_configuracoes_camera_ao_vivo(base, variaveis)
        self.assertTrue(configuracoes["pan_enabled"])
        self.assertEqual(24.0, configuracoes["pan"])
        self.assertTrue(configuracoes["brightness_enabled"])
        self.assertEqual(170.0, configuracoes["brightness"])
        self.assertFalse(configuracoes["white_balance_auto"])
        self.assertEqual(5100.0, configuracoes["white_balance"])

    def test_aplicacao_ao_vivo_nao_reinicia_camera(self):
        app = object.__new__(CameraLiveSettingsMixin)
        app.config_repository = _RepositoryFake()
        app.camera_service = _CameraServiceFake()
        app.camera_ativa = True

        aplicado = app.aplicar_configuracoes_camera_ao_vivo(
            {
                "focus_auto": False,
                "focus_enabled": True,
                "focus": 137,
            }
        )

        self.assertTrue(aplicado)
        self.assertEqual(1, len(app.camera_service.atualizacoes))
        self.assertEqual(0, app.camera_service.paradas)
        self.assertEqual(0, app.camera_service.inicios)
        self.assertEqual(
            137,
            app.camera_service.atualizacoes[0]["focus"],
        )

    def test_cancelar_reaplica_configuracao_anterior_sem_reconectar(self):
        app = object.__new__(CameraLiveSettingsMixin)
        app.config_repository = _RepositoryFake()
        app.camera_service = _CameraServiceFake()
        app.camera_ativa = True

        app.restaurar_configuracoes_camera_ao_vivo(
            {
                "focus_auto": True,
                "focus_enabled": False,
                "focus": 0,
            }
        )
        self.assertEqual(1, len(app.camera_service.atualizacoes))
        self.assertEqual(0, app.camera_service.paradas)
        self.assertEqual(0, app.camera_service.inicios)

    def test_slider_usa_debounce_curto_e_trace(self):
        self.assertGreaterEqual(LIVE_CAMERA_DEBOUNCE_MS, 20)
        self.assertLessEqual(LIVE_CAMERA_DEBOUNCE_MS, 100)
        modulo = inspect.getmodule(construir_configuracoes_camera_ao_vivo)
        fonte = inspect.getsource(modulo)
        self.assertIn('trace_add("write", agendar_aplicacao)', fonte)
        self.assertIn("callback_cancelar_camera_ao_vivo", fonte)
        self.assertIn("callback_status_camera_ao_vivo", fonte)

    def test_mixin_nao_persiste_durante_preview(self):
        fonte = inspect.getsource(
            CameraLiveSettingsMixin.aplicar_configuracoes_camera_ao_vivo
        )
        self.assertIn("atualizar_configuracoes_camera", fonte)
        self.assertNotIn("salvar_configuracoes", fonte)
        self.assertNotIn("parar_tela_ao_vivo", fonte)
        self.assertNotIn("iniciar_tela_ao_vivo", fonte)


if __name__ == "__main__":
    unittest.main()
