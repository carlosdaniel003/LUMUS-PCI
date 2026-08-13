from __future__ import annotations

from src.platform.camera_live_control_service import (
    CameraLiveControlServiceMixin,
)
from src.platform.fixed_full_hd_camera_service import (
    FixedFullHdCameraService,
)


class LiveFixedFullHdCameraService(
    CameraLiveControlServiceMixin,
    FixedFullHdCameraService,
):
    """Perfil final com transporte estável e controles pontuais ao vivo."""

    def _preparar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> dict:
        if getattr(self, "_windows_native_mode", False):
            return self._windows_native_settings(configuracoes_camera)
        return self._fixed_settings(configuracoes_camera)
