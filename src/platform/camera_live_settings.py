from __future__ import annotations

from src.ui.main_window_parts.settings.abrir_janela_configuracoes_ao_vivo import (
    abrir_janela_configuracoes_ao_vivo,
)


class CameraLiveSettingsMixin:
    """Aplica controles da aba Câmera sem salvar ou reiniciar o stream."""

    def abrir_configuracoes(self) -> None:
        camera_service = getattr(self, "camera_service", None)
        estado_conectada = getattr(
            camera_service,
            "ESTADO_CONECTADA",
            "conectada",
        )
        camera_conectada = bool(
            getattr(self, "camera_ativa", False)
            and camera_service is not None
            and getattr(self, "camera_estado_anterior", None) == estado_conectada
        )

        status_controles_camera = {}
        if camera_service is not None:
            try:
                status_controles_camera = (
                    camera_service.obter_status_controles_camera()
                )
            except Exception:
                status_controles_camera = {}

        abrir_janela_configuracoes_ao_vivo(
            self.view,
            salvar_resultados_analise=self.salvar_resultados_analise,
            raio_atual_px=self.raio_atual_px,
            configuracoes_camera=self.configuracoes_camera,
            camera_conectada=camera_conectada,
            status_controles_camera=status_controles_camera,
            callback_salvar=self.salvar_configuracoes_sistema,
            callback_camera_ao_vivo=self.aplicar_configuracoes_camera_ao_vivo,
            callback_cancelar_camera_ao_vivo=(
                self.restaurar_configuracoes_camera_ao_vivo
            ),
            callback_status_camera_ao_vivo=(
                self.obter_status_configuracoes_camera_ao_vivo
            ),
        )

    def _normalizar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> dict:
        origem = dict(configuracoes_camera or {})
        normalizar = getattr(
            self.config_repository,
            "normalizar_configuracoes_camera",
            None,
        )
        if callable(normalizar):
            try:
                return dict(normalizar(origem))
            except Exception:
                pass
        return origem

    def aplicar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> bool:
        """Envia o estado atual da UI para a câmera, sem persistir em disco."""
        camera_service = getattr(self, "camera_service", None)
        if camera_service is None or not getattr(self, "camera_ativa", False):
            return False

        configuracoes = self._normalizar_configuracoes_camera_ao_vivo(
            configuracoes_camera
        )
        try:
            camera_service.atualizar_configuracoes_camera(configuracoes)
        except Exception:
            return False

        # ThreadedRaspberryPi3CameraService marca os controles como pendentes.
        # A própria thread que já possui o VideoCapture faz os capture.set() no
        # próximo frame, evitando release(), reconexão ou disputa entre threads.
        return True

    def restaurar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> bool:
        """Restaura na câmera os valores anteriores quando a janela é cancelada."""
        return self.aplicar_configuracoes_camera_ao_vivo(
            configuracoes_camera
        )

    def obter_status_configuracoes_camera_ao_vivo(self) -> dict:
        camera_service = getattr(self, "camera_service", None)
        if camera_service is None:
            return {}
        try:
            return dict(camera_service.obter_status_controles_camera())
        except Exception:
            return {}
