from __future__ import annotations

import src.platform.fixed_full_hd_camera_service as fixed_camera_module
from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)
from src.ui.main_window_parts.settings.camera_live_ui_behavior import (
    abrir_janela_configuracoes_sem_saltos,
)


# raspberry_pi3_production_app importa CameraLiveSettingsMixin antes de importar
# FixedFullHdCameraService. Substituímos o símbolo do módulo nesse ponto para o
# perfil display receber o serviço estendido sem alterar a estrutura do app.
fixed_camera_module.FixedFullHdCameraService = LiveFixedFullHdCameraService


class CameraLiveSettingsMixin:
    """Aplica controles da aba Camera sem salvar ou reiniciar o stream."""

    def abrir_configuracoes(self) -> None:
        camera_service = getattr(self, "camera_service", None)
        estado_conectada = getattr(camera_service, "ESTADO_CONECTADA", "conectada")
        camera_conectada = bool(
            getattr(self, "camera_ativa", False)
            and camera_service is not None
            and getattr(self, "camera_estado_anterior", None) == estado_conectada
        )

        status_controles_camera = {}
        valores_hardware = {}
        if camera_service is not None:
            try:
                status_controles_camera = camera_service.obter_status_controles_camera()
            except Exception:
                status_controles_camera = {}
            obter_valores = getattr(
                camera_service,
                "obter_valores_controles_camera_ao_vivo",
                None,
            )
            if callable(obter_valores):
                try:
                    valores_hardware = dict(obter_valores())
                except Exception:
                    valores_hardware = {}

        configuracoes_interface = dict(self.configuracoes_camera or {})
        for nome, valor in valores_hardware.items():
            if not bool(configuracoes_interface.get(f"{nome}_enabled", False)):
                configuracoes_interface[nome] = valor

        self._camera_live_ultima_config = self._normalizar_configuracoes_camera_ao_vivo(
            configuracoes_interface
        )

        abrir_janela_configuracoes_sem_saltos(
            self.view,
            salvar_resultados_analise=self.salvar_resultados_analise,
            raio_atual_px=self.raio_atual_px,
            configuracoes_camera=configuracoes_interface,
            camera_conectada=camera_conectada,
            status_controles_camera=status_controles_camera,
            callback_salvar=self.salvar_configuracoes_sistema,
            callback_camera_ao_vivo=self.aplicar_configuracoes_camera_ao_vivo,
            callback_cancelar_camera_ao_vivo=self.restaurar_configuracoes_camera_ao_vivo,
            callback_status_camera_ao_vivo=self.obter_status_configuracoes_camera_ao_vivo,
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

    @staticmethod
    def _chaves_camera_alteradas(anterior: dict, atual: dict) -> list[str]:
        chaves = [
            chave
            for chave, valor in atual.items()
            if anterior.get(chave) != valor
        ]
        chaves.extend(chave for chave in anterior if chave not in atual)
        return chaves

    def _enviar_configuracoes_camera_ao_vivo(self, configuracoes: dict) -> bool:
        camera_service = getattr(self, "camera_service", None)
        if camera_service is None or not getattr(self, "camera_ativa", False):
            return False

        anterior = dict(
            getattr(
                self,
                "_camera_live_ultima_config",
                self.configuracoes_camera or {},
            )
        )
        chaves_alteradas = self._chaves_camera_alteradas(anterior, configuracoes)
        self._camera_live_ultima_config = dict(configuracoes)
        if not chaves_alteradas:
            return True

        aplicar_pontual = getattr(
            camera_service,
            "atualizar_configuracoes_camera_ao_vivo",
            None,
        )
        try:
            if callable(aplicar_pontual):
                aplicar_pontual(configuracoes, chaves_alteradas)
            else:
                camera_service.atualizar_configuracoes_camera(configuracoes)
        except Exception:
            return False
        return True

    def aplicar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> bool:
        configuracoes = self._normalizar_configuracoes_camera_ao_vivo(
            configuracoes_camera
        )
        return self._enviar_configuracoes_camera_ao_vivo(configuracoes)

    def restaurar_configuracoes_camera_ao_vivo(
        self,
        configuracoes_camera: dict | None,
    ) -> bool:
        configuracoes = self._normalizar_configuracoes_camera_ao_vivo(
            configuracoes_camera
        )
        return self._enviar_configuracoes_camera_ao_vivo(configuracoes)

    def obter_status_configuracoes_camera_ao_vivo(self) -> dict:
        camera_service = getattr(self, "camera_service", None)
        if camera_service is None:
            return {}
        try:
            return dict(camera_service.obter_status_controles_camera())
        except Exception:
            return {}
