from __future__ import annotations

import sys


LINUX_F2_FIXED_RESOLUTION = (640, 480)


class LinuxF2FixedResolutionMixin:
    """Barreira de segurança exclusiva da Produção F2 no Linux.

    O modo PCI LED em produção deixa de tratar resolução como algo adaptável:
    no Linux a resolução operacional é sempre 640x480. Frames diferentes são
    rejeitados e a sincronização dinâmica de máscaras fica bloqueada enquanto
    o F2 estiver ativo, impedindo deslocamento/redimensionamento de ROIs por uma
    renegociação inesperada do driver.

    Windows e o subsistema Display F3 não usam esta regra.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._linux_f2_resolution_lock_active = False
        super().__init__(*args, **kwargs)

    @staticmethod
    def _linux_f2_runtime() -> bool:
        return sys.platform.startswith("linux")

    def _linux_f2_deve_forcar_640(self, projeto: str | None = None) -> bool:
        if not self._linux_f2_runtime():
            return False
        if self._linux_f2_resolution_lock_active:
            return True
        nome = str(
            projeto
            or getattr(self, "projeto_led_ativo", "")
            or ""
        ).strip()
        # Um Projeto LED explicitamente carregado no Linux também é preparado
        # em 640x480, para que a edição e a produção usem a mesma geometria.
        return bool(nome)

    def _obter_resolucao_mestra_projeto(self, projeto: str | None = None):
        if self._linux_f2_deve_forcar_640(projeto):
            return LINUX_F2_FIXED_RESOLUTION
        return super()._obter_resolucao_mestra_projeto(projeto)

    def _salvar_resolucao_mestra_do_projeto_atual(
        self,
        projeto: str,
        resolucao,
    ) -> bool:
        if self._linux_f2_runtime() and str(projeto or "").strip():
            resolucao = LINUX_F2_FIXED_RESOLUTION
        return super()._salvar_resolucao_mestra_do_projeto_atual(
            projeto,
            resolucao,
        )

    def obter_parametros_camera_dinamicos(self) -> tuple[int, int, int]:
        largura, altura, fps = super().obter_parametros_camera_dinamicos()
        if self._linux_f2_deve_forcar_640():
            largura, altura = LINUX_F2_FIXED_RESOLUTION
        return int(largura), int(altura), int(fps)

    def _linux_f2_travar_servico(self) -> None:
        if not self._linux_f2_runtime():
            return
        resolucao = LINUX_F2_FIXED_RESOLUTION
        self._resolucao_mestra_projeto_ativa = resolucao
        if self._linux_f2_resolution_lock_active:
            self._resolucao_mestra_producao = resolucao
        try:
            self._atualizar_config_camera_para_resolucao_mestra(resolucao)
        except Exception:
            pass
        try:
            self._travar_servico_na_resolucao_mestra(
                getattr(self, "camera_service", None),
                resolucao,
            )
        except Exception:
            pass

    def _linux_f2_frame_640_valido(self) -> bool:
        frame = getattr(self, "camera_frame_atual", None)
        if frame is None or not getattr(frame, "size", 0):
            return False
        try:
            altura, largura = frame.shape[:2]
        except Exception:
            return False
        return (int(largura), int(altura)) == LINUX_F2_FIXED_RESOLUTION

    def _linux_f2_bloquear_frame_invalido(self) -> None:
        self._linux_f2_travar_servico()
        try:
            self._mostrar_erro_resolucao_mestra_producao()
        except Exception:
            pass

    def abrir_tela_operacao(self) -> None:
        if not self._linux_f2_runtime():
            return super().abrir_tela_operacao()

        self._linux_f2_resolution_lock_active = True
        self._resolucao_mestra_projeto_ativa = LINUX_F2_FIXED_RESOLUTION
        self._resolucao_mestra_producao = LINUX_F2_FIXED_RESOLUTION

        # Faz a troca antes de ativar a tela de produção. Se a câmera já estiver
        # em 640x480, ProjectMasterResolution não reinicia nem reconecta.
        self._aplicar_resolucao_mestra_projeto(
            getattr(self, "projeto_led_ativo", None),
            reiniciar_se_necessario=True,
        )
        self._linux_f2_travar_servico()
        return super().abrir_tela_operacao()

    def fechar_tela_operacao(self) -> None:
        try:
            return super().fechar_tela_operacao()
        finally:
            self._linux_f2_resolution_lock_active = False

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        # Em F2/Linux a geometria carregada para 640x480 é imutável durante a
        # sessão. Nunca transformar centro, raio, largura, altura ou vértices em
        # resposta a uma alteração de resolução do stream.
        if (
            self._linux_f2_runtime()
            and bool(getattr(self, "operacao_ativa", False))
        ):
            return None
        return super()._synchronize_masks_with_current_frame(
            force=force,
            schedule_operation_prepare=schedule_operation_prepare,
        )

    def preparar_tela_operacao(self) -> None:
        if (
            self._linux_f2_runtime()
            and bool(getattr(self, "operacao_ativa", False))
        ):
            self._linux_f2_travar_servico()
            frame = getattr(self, "camera_frame_atual", None)
            if frame is not None and getattr(frame, "size", 0):
                if not self._linux_f2_frame_640_valido():
                    self._linux_f2_bloquear_frame_invalido()
                    agendar = getattr(self, "_agendar_preparo_operacao", None)
                    if callable(agendar):
                        try:
                            agendar(150)
                        except Exception:
                            pass
                    return None
        return super().preparar_tela_operacao()

    def disparar_inspecao_operacao(self) -> None:
        if (
            self._linux_f2_runtime()
            and bool(getattr(self, "operacao_ativa", False))
        ):
            self._linux_f2_travar_servico()
            if not self._linux_f2_frame_640_valido():
                self._linux_f2_bloquear_frame_invalido()
                return None
        return super().disparar_inspecao_operacao()
