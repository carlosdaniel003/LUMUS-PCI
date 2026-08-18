import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)
from src.platform.windows_camera_compatibility import (
    WindowsCameraCompatibilityMixin,
)
from src.ui.main_window_parts.settings.camera_runtime_profile_ui import (
    _aplicar_perfil_real,
)


class _CaptureFrames:
    def __init__(self, resolucoes):
        self._resolucoes = list(resolucoes)
        self._indice = 0

    def read(self):
        if not self._resolucoes:
            return False, None
        indice = min(self._indice, len(self._resolucoes) - 1)
        largura, altura = self._resolucoes[indice]
        self._indice += 1
        return True, SimpleNamespace(shape=(altura, largura, 3))


class _BaseProbe:
    ESTADO_ESTABILIZANDO = "estabilizando"

    def __init__(self):
        self.largura = 1920
        self.altura = 1080
        self.fps = 20
        self.formato_camera = "MJPG"
        self.perfil_automatico = False
        self._resolucao_solicitada = (1920, 1080)
        self._fps_solicitado = 20
        self._formato_solicitado = "MJPG"
        self._chamadas_abrir = []
        self._estado = None

    @staticmethod
    def _normalizar_frame(frame):
        return frame

    @staticmethod
    def _frame_basico_valido(frame):
        return frame is not None

    def _capture_entrega_frame_inicial(self, capture):
        sucesso, frame = capture.read()
        return bool(sucesso and frame is not None)

    def _abrir_camera(self):
        self._chamadas_abrir.append(
            (self.perfil_automatico, self.fps, self.formato_camera)
        )
        # Simula: perfil explícito falha, modo automático funciona.
        return bool(self.perfil_automatico)

    def _definir_estado(self, estado, mensagem):
        self._estado = (estado, mensagem)

    def obter_diagnostico_fluxo(self):
        return {}


class _ServicoCompatibilidadeFake(
    WindowsCameraCompatibilityMixin,
    _BaseProbe,
):
    pass


class WindowsCameraResolutionTests(unittest.TestCase):
    def test_servico_final_inclui_compatibilidade_windows(self):
        self.assertTrue(
            issubclass(
                LiveFixedFullHdCameraService,
                WindowsCameraCompatibilityMixin,
            )
        )

    def test_full_hd_explicito_nao_e_convertido_para_auto(self):
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
        self.assertEqual("manual", configuracoes["fps_mode"])
        self.assertEqual(20, configuracoes["fps"])
        self.assertEqual("MJPG", configuracoes["format"])

    def test_auto_continua_disponivel_como_negociacao_nativa(self):
        configuracoes = LiveFixedFullHdCameraService._windows_native_settings(
            {
                "resolution_mode": "auto",
                "width": 1920,
                "height": 1080,
                "fps_mode": "manual",
                "fps": 20,
                "format": "MJPG",
            }
        )
        self.assertEqual("auto", configuracoes["resolution_mode"])
        self.assertEqual("auto", configuracoes["fps_mode"])
        self.assertEqual(0, configuracoes["fps"])
        self.assertEqual("AUTO", configuracoes["format"])

    def test_probe_ignora_640_e_aceita_1920_quando_solicitado(self):
        service = _ServicoCompatibilidadeFake()
        service._windows_exigir_resolucao_solicitada = True
        capture = _CaptureFrames(
            [(640, 480), (640, 480), (1920, 1080)]
        )
        with patch(
            "src.platform.windows_camera_compatibility.sys.platform",
            "win32",
        ):
            self.assertTrue(service._capture_entrega_frame_inicial(capture))
        self.assertEqual(
            (1920, 1080),
            service._windows_ultima_resolucao_probe,
        )

    def test_se_perfil_explicito_falhar_abre_auto_sem_perder_alvo(self):
        service = _ServicoCompatibilidadeFake()
        with patch(
            "src.platform.windows_camera_compatibility.sys.platform",
            "win32",
        ):
            self.assertTrue(service._abrir_camera())

        self.assertEqual(
            [(False, 20, "MJPG"), (True, 0, "AUTO")],
            service._chamadas_abrir,
        )
        self.assertFalse(service.perfil_automatico)
        self.assertEqual(20, service.fps)
        self.assertEqual("MJPG", service.formato_camera)
        self.assertEqual((1920, 1080), service._resolucao_solicitada)
        self.assertTrue(service._windows_fallback_automatico_ativo)

    def test_perfil_real_nao_sobrescreve_seletor_configurado(self):
        fonte = inspect.getsource(_aplicar_perfil_real)
        self.assertNotIn("select.set", fonte)
        self.assertNotIn("spin.config(state=tk.DISABLED)", fonte)
        self.assertIn('text="ATUAL  •  "', fonte)


if __name__ == "__main__":
    unittest.main()
