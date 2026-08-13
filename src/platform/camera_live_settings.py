from __future__ import annotations

from src.platform.verified_live_camera_service import (
    instalar_validacao_controles_camera,
)
from src.ui.main_window_parts.settings.camera_runtime_profile_ui import (
    abrir_janela_configuracoes_com_status_real,
)


instalar_validacao_controles_camera()


class CameraLiveSettingsMixin:
    """Aplica controles da aba Camera sem salvar ou reiniciar o stream."""

    @staticmethod
    def _obter_perfil_camera_real(camera_service) -> dict:
        if camera_service is None:
            return {}

        perfil = {}
        try:
            snapshot = camera_service.obter_snapshot()
        except Exception:
            snapshot = None

        if snapshot is not None:
            resolucao = getattr(snapshot, "resolucao", None)
            if resolucao:
                perfil["resolucao"] = tuple(resolucao)
            fps = getattr(snapshot, "fps_real", None)
            if fps is not None:
                perfil["fps"] = fps
            formato = getattr(snapshot, "formato_real", None)
            if formato:
                perfil["formato"] = formato

        try:
            diagnostico = camera_service.obter_diagnostico_fluxo()
        except Exception:
            diagnostico = {}

        if not perfil.get("fps"):
            perfil["fps"] = diagnostico.get("fps_medido")
        if not perfil.get("formato"):
            perfil["formato"] = diagnostico.get("backend_formato")
        perfil["backend"] = (
            diagnostico.get("backend_ativo")
            or getattr(camera_service, "_backend_name", "")
        )
        perfil["indice"] = getattr(camera_service, "indice_camera", None)
        return perfil

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
        perfil_camera_real = self._obter_perfil_camera_real(camera_service)
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

        # Mantém a cadeia cooperativa para que ProjectReferenceSetsMixin continue
        # reconstruindo as referências múltiplas GLOBAL/PROJETO na mesma janela.
        view = self.view
        abrir_view_original = view.abrir_janela_configuracoes

        def abrir_view_ao_vivo(*args, **kwargs):
            kwargs["configuracoes_camera"] = configuracoes_interface
            kwargs["camera_conectada"] = camera_conectada
            kwargs["status_controles_camera"] = status_controles_camera
            return abrir_janela_configuracoes_com_status_real(
                view,
                *args,
                perfil_camera_real=perfil_camera_real,
                callback_camera_ao_vivo=self.aplicar_configuracoes_camera_ao_vivo,
                callback_cancelar_camera_ao_vivo=(
                    self.restaurar_configuracoes_camera_ao_vivo
                ),
                callback_status_camera_ao_vivo=(
                    self.obter_status_configuracoes_camera_ao_vivo
                ),
                **kwargs,
            )

        view.abrir_janela_configuracoes = abrir_view_ao_vivo
        try:
            return super().abrir_configuracoes()
        finally:
            view.abrir_janela_configuracoes = abrir_view_original

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
                getattr(self, "configuracoes_camera", {}) or {},
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
