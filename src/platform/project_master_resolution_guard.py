from __future__ import annotations


class ProjectMasterResolutionGuardMixin:
    """Ordena e protege a resolução mestre do projeto ativo.

    A camada principal de resolução mestre intercepta o fluxo de câmera. Este
    guard garante a ordem temporal, a base correta de persistência das ROIs e
    impede que a janela geral de câmera substitua silenciosamente a resolução
    mestre de um projeto já definido.
    """

    def _selecionar_projeto_led_existente(self, projetos: list[str]):
        selecionado = super()._selecionar_projeto_led_existente(projetos)
        if selecionado is None:
            return None

        # O modo da câmera é decidido antes que LedProjectManagerMixin receba o
        # nome e carregue/desenhe as ROIs desse projeto.
        self._aplicar_resolucao_mestra_projeto(
            selecionado,
            reiniciar_se_necessario=True,
        )
        return selecionado

    def _salvar_leds_no_projeto(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        resolucao = self._obter_resolucao_edicao_atual()
        if resolucao is not None:
            # SegmentProjectGeometryPersistenceMixin usa esses campos como base
            # para normalizar centro, dimensões e vértices. Reafirmá-los aqui
            # impede que um valor antigo sobreviva a uma troca de câmera.
            self.largura_original = int(resolucao[0])
            self.altura_original = int(resolucao[1])

        return super()._salvar_leds_no_projeto(
            nome_projeto,
            parent=parent,
            confirmar_substituicao=confirmar_substituicao,
        )

    def salvar_configuracoes_sistema(
        self,
        salvar_resultados_analise: bool,
        raio_configurado_px: int | None = None,
        configuracoes_camera: dict | None = None,
    ) -> None:
        """Mantém a resolução mestre e deixa os demais controles editáveis."""
        resolucao = (
            getattr(self, "_resolucao_mestra_projeto_ativa", None)
            or self._atualizar_resolucao_mestra_projeto_ativa()
        )
        configuracoes = (
            dict(configuracoes_camera)
            if isinstance(configuracoes_camera, dict)
            else configuracoes_camera
        )

        if resolucao is not None and isinstance(configuracoes, dict):
            configuracoes.update(
                {
                    "resolution_mode": "custom",
                    "width": int(resolucao[0]),
                    "height": int(resolucao[1]),
                }
            )

        return super().salvar_configuracoes_sistema(
            salvar_resultados_analise,
            raio_configurado_px=raio_configurado_px,
            configuracoes_camera=configuracoes,
        )
