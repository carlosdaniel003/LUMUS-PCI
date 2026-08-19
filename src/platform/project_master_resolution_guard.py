from __future__ import annotations


class ProjectMasterResolutionGuardMixin:
    """Ordena resolução mestre antes de carregar/salvar geometria de projeto.

    A camada principal de resolução mestre intercepta o fluxo de câmera. Este
    guard apenas garante a ordem temporal: a câmera recebe o modo do projeto
    assim que o operador confirma a seleção, antes de o gerenciador legado
    carregar as ROIs; e a geometria salva usa a resolução real observada no
    instante do salvamento.
    """

    def _selecionar_projeto_led_existente(self, projetos: list[str]):
        selecionado = super()._selecionar_projeto_led_existente(projetos)
        if selecionado is None:
            return None

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
