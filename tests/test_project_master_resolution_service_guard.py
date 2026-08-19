import threading
import unittest

from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)


class ProjectMasterResolutionServiceGuardTests(unittest.TestCase):
    def _service_travado(self):
        service = LiveFixedFullHdCameraService.__new__(
            LiveFixedFullHdCameraService
        )
        service._lock = threading.RLock()
        service._resolucao_mestra_travada = (640, 480)
        service._configuracoes_camera = {
            "resolution_mode": "custom",
            "width": 640,
            "height": 480,
            "fps_mode": "manual",
            "fps": 20,
            "format": "MJPG",
        }
        service.largura = 640
        service.altura = 480
        service.modo_resolucao = "custom"
        service.perfil_automatico = False
        service._resolucao_solicitada = (640, 480)
        service._controles_pendentes = False
        service._controles_automaticos_travados = True
        return service

    def test_salvar_controle_nao_troca_master_640_para_1920(self):
        service = self._service_travado()

        service.atualizar_configuracoes_camera(
            {
                "resolution_mode": "custom",
                "width": 1920,
                "height": 1080,
                "fps_mode": "manual",
                "fps": 20,
                "format": "MJPG",
                "gain_enabled": True,
                "gain": 21,
            }
        )

        config = service.obter_configuracoes_camera()
        self.assertEqual((640, 480), (service.largura, service.altura))
        self.assertEqual((640, 480), service._resolucao_solicitada)
        self.assertEqual("custom", config["resolution_mode"])
        self.assertEqual((640, 480), (config["width"], config["height"]))
        self.assertTrue(config["gain_enabled"])
        self.assertEqual(21.0, config["gain"])
        self.assertTrue(service._controles_pendentes)

    def test_atualizacao_generica_nao_remove_trava(self):
        service = self._service_travado()

        service.atualizar_configuracoes_camera({"rotation": 180})

        self.assertEqual((640, 480), service.obter_resolucao_travada())
        config = service.obter_configuracoes_camera()
        self.assertEqual((640, 480), (config["width"], config["height"]))
        self.assertEqual(180, config["rotation"])


if __name__ == "__main__":
    unittest.main()
