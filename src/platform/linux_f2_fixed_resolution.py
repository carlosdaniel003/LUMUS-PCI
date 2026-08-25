from __future__ import annotations

import sys


LINUX_F2_FIXED_RESOLUTION = (640, 480)


class LinuxF2FixedResolutionMixin:
    """Barreira de segurança da geometria F2 no Linux.

    No JIG Linux o transporte da câmera já nasce em 640x480, antes mesmo de
    carregar um Projeto LED. Assim não existe mais uma primeira geometria em
    1280x720/1920x1080 capaz de esticar ROIs quando o projeto 640x480 entra.

    Durante a Produção F2 a resolução operacional continua estritamente
    640x480: frames diferentes são rejeitados e a sincronização dinâmica de
    máscaras fica bloqueada, impedindo deslocamento/redimensionamento de ROIs
    por uma renegociação inesperada do driver.

    Windows não usa esta regra. A lógica funcional do Display F3 não é alterada;
    somente o transporte inicial compartilhado da câmera no Linux passa a abrir
    diretamente em 640x480.
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

    def _atualizar_resolucao_mestra_projeto_ativa(
        self,
        projeto: str | None = None,
    ):
        if self._linux_f2_runtime() and self._linux_f2_resolution_lock_active:
            self._resolucao_mestra_projeto_nome = str(
                projeto
                or getattr(self, "projeto_led_ativo", "")
                or ""
            ).strip()
            self._resolucao_mestra_projeto_ativa = LINUX_F2_FIXED_RESOLUTION
            return LINUX_F2_FIXED_RESOLUTION
        return super()._atualizar_resolucao_mestra_projeto_ativa(projeto)

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
        # No Linux não esperamos mais um projeto ser carregado para corrigir a
        # resolução. O primeiro frame da sessão já deve pertencer ao mesmo
        # sistema de coordenadas 640x480 usado pelas ROIs do F2.
        if self._linux_f2_runtime():
            largura, altura = LINUX_F2_FIXED_RESOLUTION
        return int(largura), int(altura), int(fps)

    def _aplicar_resolucao_mestra_projeto(
        self,
        projeto: str | None = None,
        reiniciar_se_necessario: bool = True,
    ) -> bool:
        if not (
            self._linux_f2_runtime()
            and self._linux_f2_resolution_lock_active
        ):
            return super()._aplicar_resolucao_mestra_projeto(
                projeto,
                reiniciar_se_necessario=reiniciar_se_necessario,
            )

        resolucao = LINUX_F2_FIXED_RESOLUTION
        self._resolucao_mestra_projeto_nome = str(
            projeto
            or getattr(self, "projeto_led_ativo", "")
            or ""
        ).strip()
        self._resolucao_mestra_projeto_ativa = resolucao
        self._resolucao_mestra_producao = resolucao
        self._atualizar_config_camera_para_resolucao_mestra(resolucao)

        service = getattr(self, "camera_service", None)
        camera_ativa = bool(getattr(self, "camera_ativa", False))
        if camera_ativa and service is not None:
            ja_esta = getattr(self, "_camera_ja_esta_na_resolucao", None)
            if callable(ja_esta):
                try:
                    if ja_esta(resolucao):
                        self._travar_servico_na_resolucao_mestra(service, resolucao)
                        return False
                except Exception:
                    pass

        if camera_ativa and reiniciar_se_necessario:
            reiniciar = getattr(self, "_reiniciar_camera_para_resolucao_mestra", None)
            if callable(reiniciar):
                try:
                    return bool(reiniciar(resolucao))
                except Exception:
                    pass

        self._travar_servico_na_resolucao_mestra(service, resolucao)
        return False

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

    def _mask_guard_current_resolution(self):
        """Impede o segundo guard de geometria de seguir um frame renegociado."""
        if (
            self._linux_f2_runtime()
            and (
                self._linux_f2_resolution_lock_active
                or bool(getattr(self, "operacao_ativa", False))
            )
        ):
            return LINUX_F2_FIXED_RESOLUTION
        return super()._mask_guard_current_resolution()

    def abrir_tela_operacao(self) -> None:
        if not self._linux_f2_runtime():
            return super().abrir_tela_operacao()

        self._linux_f2_resolution_lock_active = True
        self._resolucao_mestra_projeto_ativa = LINUX_F2_FIXED_RESOLUTION
        self._resolucao_mestra_producao = LINUX_F2_FIXED_RESOLUTION

        # Faz a troca antes de ativar a tela de produção. Como a câmera Linux
        # agora já nasce em 640x480, este caminho normalmente apenas confirma
        # a mesma trava sem reiniciar nem renegociar o stream.
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

    def atualizar_frame_camera(self) -> None:
        if not (
            self._linux_f2_runtime()
            and bool(getattr(self, "operacao_ativa", False))
        ):
            return super().atualizar_frame_camera()

        frame_anterior = getattr(self, "camera_frame_atual", None)
        frame_anterior_valido = False
        if frame_anterior is not None and getattr(frame_anterior, "size", 0):
            try:
                altura, largura = frame_anterior.shape[:2]
                frame_anterior_valido = (
                    int(largura),
                    int(altura),
                ) == LINUX_F2_FIXED_RESOLUTION
            except Exception:
                frame_anterior_valido = False

        imagem_anterior = getattr(self, "imagem_original", None)
        largura_anterior = getattr(self, "largura_original", None)
        altura_anterior = getattr(self, "altura_original", None)

        resultado = super().atualizar_frame_camera()

        frame_atual = getattr(self, "camera_frame_atual", None)
        if frame_atual is not None and getattr(frame_atual, "size", 0):
            if not self._linux_f2_frame_640_valido():
                # Mesmo que um backend consiga publicar um frame renegociado,
                # ele não vira a nova base visual/geométrica do F2.
                self.camera_frame_atual = (
                    frame_anterior if frame_anterior_valido else None
                )
                self.imagem_original = imagem_anterior
                if largura_anterior is not None:
                    self.largura_original = largura_anterior
                if altura_anterior is not None:
                    self.altura_original = altura_anterior
                self._linux_f2_travar_servico()
        return resultado

    def _atualizar_preview_operacao(self) -> None:
        if (
            self._linux_f2_runtime()
            and bool(getattr(self, "operacao_ativa", False))
        ):
            frame = getattr(self, "camera_frame_atual", None)
            if frame is not None and getattr(frame, "size", 0):
                if not self._linux_f2_frame_640_valido():
                    self._operacao_preview_after_id = None
                    try:
                        self.operacao_window.set_preview_status(
                            "Frame rejeitado • F2 Linux exige 640x480",
                            "#FCA5A5",
                        )
                    except Exception:
                        pass
                    self._linux_f2_travar_servico()
                    agendar = getattr(self, "_agendar_preview_operacao", None)
                    if callable(agendar):
                        try:
                            agendar()
                        except Exception:
                            pass
                    return None
        return super()._atualizar_preview_operacao()

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
                agendar = getattr(self, "_agendar_preparo_operacao", None)
                if callable(agendar):
                    try:
                        agendar(150)
                    except Exception:
                        pass
                return None
        return super().disparar_inspecao_operacao()
