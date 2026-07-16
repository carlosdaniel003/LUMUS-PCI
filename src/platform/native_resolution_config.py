from __future__ import annotations

from src.platform.raspberry_pi3_settings import (
    CAMERA_FPS,
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
)


class NativeResolutionConfigMixin:
    """Mantém desenvolvimento e Produção F2 no mesmo perfil de captura UHD."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fixar_configuracao_camera_nativa()

    def _fixar_configuracao_camera_nativa(self) -> None:
        configuracoes = dict(
            getattr(self, "configuracoes_camera", {}) or {}
        )
        desejadas = {
            "resolution_mode": "uhd",
            "width": CAMERA_WIDTH,
            "height": CAMERA_HEIGHT,
            "fps_mode": "manual",
            "fps": CAMERA_FPS,
            "format": "MJPG",
        }
        alterado = any(
            configuracoes.get(chave) != valor
            for chave, valor in desejadas.items()
        )
        configuracoes.update(desejadas)
        self.configuracoes_camera = configuracoes

        if not alterado:
            return

        try:
            self.configuracao_atual = (
                self.config_repository.salvar_configuracoes_sistema(
                    salvar_resultados_analise=(
                        self.salvar_resultados_analise
                    ),
                    raio_atual_px=self.raio_atual_px,
                    configuracoes_camera=configuracoes,
                )
            )
            self.configuracoes_camera = (
                self.config_repository.obter_configuracoes_camera()
            )
        except Exception:
            # O perfil em memória continua válido mesmo quando a configuração
            # local estiver temporariamente sem permissão de escrita.
            self.configuracoes_camera = configuracoes
