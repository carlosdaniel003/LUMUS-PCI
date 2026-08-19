from __future__ import annotations

import src.platform.raspberry_pi3_profile as raspberry_pi3_profile


class ProjectMasterResolutionMixin:
    """Mantém câmera e ROIs no modo de captura salvo com cada projeto."""

    def __init__(self, *args, **kwargs) -> None:
        self._resolucao_mestra_projeto_ativa: tuple[int, int] | None = None
        self._resolucao_mestra_projeto_nome = ""
        self._reiniciando_camera_resolucao_mestra = False
        self._resolucao_mestra_producao: tuple[int, int] | None = None
        super().__init__(*args, **kwargs)
        self._atualizar_resolucao_mestra_projeto_ativa()

    @staticmethod
    def _resolucao_frame(frame) -> tuple[int, int] | None:
        if frame is None or not getattr(frame, "size", 0):
            return None
        altura, largura = frame.shape[:2]
        if largura <= 0 or altura <= 0:
            return None
        return int(largura), int(altura)

    def _obter_resolucao_mestra_projeto(
        self,
        projeto: str | None = None,
    ) -> tuple[int, int] | None:
        obter = getattr(
            self.config_repository,
            "obter_resolucao_mestra_projeto_led",
            None,
        )
        if not callable(obter):
            return None
        try:
            resolucao = obter(projeto=projeto)
        except TypeError:
            resolucao = obter(projeto)
        except Exception:
            return None
        if not resolucao or len(resolucao) < 2:
            return None
        try:
            largura, altura = int(resolucao[0]), int(resolucao[1])
        except (TypeError, ValueError):
            return None
        if largura <= 0 or altura <= 0:
            return None
        return largura, altura

    def _atualizar_resolucao_mestra_projeto_ativa(
        self,
        projeto: str | None = None,
    ) -> tuple[int, int] | None:
        nome = str(
            projeto
            or getattr(self, "projeto_led_ativo", "")
            or ""
        ).strip()
        resolucao = self._obter_resolucao_mestra_projeto(nome or None)
        self._resolucao_mestra_projeto_nome = nome
        self._resolucao_mestra_projeto_ativa = resolucao
        return resolucao

    def _atualizar_config_camera_para_resolucao_mestra(
        self,
        resolucao: tuple[int, int] | None,
    ) -> None:
        if resolucao is None:
            return
        configuracoes = dict(getattr(self, "configuracoes_camera", {}) or {})
        configuracoes.update(
            {
                "resolution_mode": "custom",
                "width": int(resolucao[0]),
                "height": int(resolucao[1]),
            }
        )
        self.configuracoes_camera = configuracoes

    def _obter_resolucao_camera_real(self) -> tuple[int, int] | None:
        service = getattr(self, "camera_service", None)
        if service is not None:
            try:
                snapshot = service.obter_snapshot()
            except Exception:
                snapshot = None
            resolucao = getattr(snapshot, "resolucao", None)
            if resolucao and len(resolucao) >= 2:
                return int(resolucao[0]), int(resolucao[1])

        if bool(getattr(self, "camera_ativa", False)):
            return self._resolucao_frame(
                getattr(self, "camera_frame_atual", None)
            )
        return None

    def _obter_resolucao_camera_solicitada(self) -> tuple[int, int] | None:
        service = getattr(self, "camera_service", None)
        if service is None:
            return None
        try:
            snapshot = service.obter_snapshot()
        except Exception:
            return None
        resolucao = getattr(snapshot, "resolucao_solicitada", None)
        if not resolucao or len(resolucao) < 2:
            return None
        return int(resolucao[0]), int(resolucao[1])

    def _travar_servico_na_resolucao_mestra(
        self,
        service,
        resolucao: tuple[int, int] | None,
    ) -> None:
        if service is None or resolucao is None:
            return
        travar = getattr(service, "definir_resolucao_travada", None)
        if callable(travar):
            travar(int(resolucao[0]), int(resolucao[1]))

    def _camera_ja_esta_na_resolucao(
        self,
        resolucao: tuple[int, int],
    ) -> bool:
        atual = self._obter_resolucao_camera_real()
        if atual is not None:
            return atual == resolucao
        solicitada = self._obter_resolucao_camera_solicitada()
        return solicitada == resolucao

    def obter_parametros_camera_dinamicos(self) -> tuple[int, int, int]:
        largura, altura, fps = super().obter_parametros_camera_dinamicos()
        resolucao = (
            self._resolucao_mestra_projeto_ativa
            or self._atualizar_resolucao_mestra_projeto_ativa()
        )
        if resolucao is None:
            return largura, altura, fps
        return int(resolucao[0]), int(resolucao[1]), int(fps)

    @staticmethod
    def _classe_camera_com_resolucao_travada(
        classe_base: type,
        resolucao: tuple[int, int],
    ) -> type:
        largura, altura = int(resolucao[0]), int(resolucao[1])

        class CameraServiceResolucaoMestre(classe_base):
            _odin_project_master_resolution = (largura, altura)

            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                travar = getattr(self, "definir_resolucao_travada", None)
                if callable(travar):
                    travar(largura, altura)

        CameraServiceResolucaoMestre.__name__ = (
            f"{classe_base.__name__}Projeto{largura}x{altura}"
        )
        CameraServiceResolucaoMestre.__qualname__ = (
            CameraServiceResolucaoMestre.__name__
        )
        return CameraServiceResolucaoMestre

    def iniciar_tela_ao_vivo(self) -> None:
        resolucao = (
            self._resolucao_mestra_projeto_ativa
            or self._atualizar_resolucao_mestra_projeto_ativa()
        )
        if resolucao is None:
            return super().iniciar_tela_ao_vivo()

        self._atualizar_config_camera_para_resolucao_mestra(resolucao)
        classe_atual = raspberry_pi3_profile.RaspberryPi3CameraService
        classe_travada = self._classe_camera_com_resolucao_travada(
            classe_atual,
            resolucao,
        )
        raspberry_pi3_profile.RaspberryPi3CameraService = classe_travada
        try:
            resultado = super().iniciar_tela_ao_vivo()
        finally:
            raspberry_pi3_profile.RaspberryPi3CameraService = classe_atual

        # O perfil Raspberry legado ainda escreve seus defaults durante o
        # start. Reafirmamos a configuração visível sem tocar no capture.
        self._atualizar_config_camera_para_resolucao_mestra(resolucao)
        self._travar_servico_na_resolucao_mestra(
            getattr(self, "camera_service", None),
            resolucao,
        )
        return resultado

    def _reiniciar_camera_para_resolucao_mestra(
        self,
        resolucao: tuple[int, int],
    ) -> bool:
        if self._reiniciando_camera_resolucao_mestra:
            return False

        service = getattr(self, "camera_service", None)
        if service is not None and getattr(self, "indice_camera_selecionada", None) is None:
            try:
                self.indice_camera_selecionada = int(service.indice_camera)
            except Exception:
                pass

        self._reiniciando_camera_resolucao_mestra = True
        try:
            self._atualizar_config_camera_para_resolucao_mestra(resolucao)
            self.parar_tela_ao_vivo(manter_imagem=True)
            self.iniciar_tela_ao_vivo()
        finally:
            self._reiniciando_camera_resolucao_mestra = False
        return True

    def _aplicar_resolucao_mestra_projeto(
        self,
        projeto: str | None = None,
        reiniciar_se_necessario: bool = True,
    ) -> bool:
        """Retorna True somente quando foi necessário reiniciar a câmera."""
        resolucao = self._atualizar_resolucao_mestra_projeto_ativa(projeto)
        if resolucao is None:
            return False

        self._atualizar_config_camera_para_resolucao_mestra(resolucao)
        service = getattr(self, "camera_service", None)
        camera_ativa = bool(getattr(self, "camera_ativa", False))

        if camera_ativa and service is not None and self._camera_ja_esta_na_resolucao(resolucao):
            # Caso essencial: já está no modo correto. Somente instala a trava;
            # nenhum set, stop, start ou reconexão é executado.
            self._travar_servico_na_resolucao_mestra(service, resolucao)
            return False

        if camera_ativa and reiniciar_se_necessario:
            return self._reiniciar_camera_para_resolucao_mestra(resolucao)
        return False

    def _resolucao_mestra_compativel_com_frame_producao(self) -> bool:
        mestre = self._resolucao_mestra_producao
        if mestre is None:
            mestre = self._resolucao_mestra_projeto_ativa
        if mestre is None:
            return True
        atual = self._resolucao_frame(getattr(self, "camera_frame_atual", None))
        return atual is None or atual == mestre

    def _mostrar_erro_resolucao_mestra_producao(self) -> None:
        mestre = self._resolucao_mestra_producao or self._resolucao_mestra_projeto_ativa
        atual = self._resolucao_frame(getattr(self, "camera_frame_atual", None))
        if mestre is None:
            return
        texto_atual = "sem frame" if atual is None else f"{atual[0]}x{atual[1]}"
        mensagem = (
            "RESOLUÇÃO DA CÂMERA ALTERADA\n"
            f"Projeto: {mestre[0]}x{mestre[1]} | Câmera: {texto_atual}"
        )
        janela = getattr(self, "operacao_window", None)
        if janela is not None:
            try:
                janela.show_error(
                    mensagem,
                    total=int(getattr(self, "operacao_total", 0)),
                    ok_count=int(getattr(self, "operacao_ok", 0)),
                    ng_count=int(getattr(self, "operacao_ng", 0)),
                )
                janela.set_preview_status(
                    "Frame rejeitado • resolução fora do projeto",
                    "#FCA5A5",
                )
            except Exception:
                pass
        engine = getattr(self, "operacao_engine", None)
        invalidate = getattr(engine, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def abrir_tela_operacao(self) -> None:
        self._resolucao_mestra_producao = (
            self._atualizar_resolucao_mestra_projeto_ativa()
        )
        self._aplicar_resolucao_mestra_projeto(
            getattr(self, "projeto_led_ativo", None),
            reiniciar_se_necessario=True,
        )
        service = getattr(self, "camera_service", None)
        self._travar_servico_na_resolucao_mestra(
            service,
            self._resolucao_mestra_producao,
        )
        return super().abrir_tela_operacao()

    def preparar_tela_operacao(self) -> None:
        if (
            bool(getattr(self, "operacao_ativa", False))
            and not self._resolucao_mestra_compativel_com_frame_producao()
        ):
            self._mostrar_erro_resolucao_mestra_producao()
            return
        return super().preparar_tela_operacao()

    def disparar_inspecao_operacao(self) -> None:
        if (
            bool(getattr(self, "operacao_ativa", False))
            and not self._resolucao_mestra_compativel_com_frame_producao()
        ):
            self._mostrar_erro_resolucao_mestra_producao()
            return
        return super().disparar_inspecao_operacao()

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        if (
            bool(getattr(self, "operacao_ativa", False))
            and not self._resolucao_mestra_compativel_com_frame_producao()
        ):
            return
        return super()._synchronize_masks_with_current_frame(
            force=force,
            schedule_operation_prepare=schedule_operation_prepare,
        )
