from __future__ import annotations

from typing import Iterable

from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.models.led_selection import LedSelection


_PATCH_SEGMENTO_LIVRE_PERSISTENCIA = False


def copiar_mascara_absoluta_segmento_livre(led: LedSelection) -> LedSelection:
    """Nome legado; preserva pixels, base normalizada e vértices livres."""
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        centro_x_normalizado=led.centro_x_normalizado,
        centro_y_normalizado=led.centro_y_normalizado,
        raio_normalizado=led.raio_normalizado,
        largura_base=led.largura_base,
        altura_base=led.altura_base,
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def copiar_led_geometria_completa_segmento_livre(
    led: LedSelection,
) -> LedSelection:
    return copiar_mascara_absoluta_segmento_livre(led)


def assinatura_geometria_segmento_livre(
    leds: Iterable[LedSelection] | None,
) -> tuple[tuple, ...]:
    assinatura = []
    for led in leds or ():
        tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))
        if tipo == TIPO_ROI_SEGMENTO:
            pontos = tuple(
                (round(float(x), 4), round(float(y), 4))
                for x, y in (
                    getattr(led, "pontos_segmento_livre", None) or ()
                )
            )
            assinatura.append(
                (
                    str(led.id),
                    TIPO_ROI_SEGMENTO,
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                    None if getattr(led, "largura", None) is None else int(led.largura),
                    None if getattr(led, "altura", None) is None else int(led.altura),
                    round(float(getattr(led, "angulo", 0.0) or 0.0), 6),
                    pontos,
                )
            )
        else:
            assinatura.append(
                (
                    str(led.id),
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                )
            )
    return tuple(assinatura)


def _instalar_roundtrip_projeto_segmento_livre() -> None:
    """Fecha o caminho legado usado por Carregar LEDs > Salvar selecionados.

    O gerenciador de projetos chama ``super().salvar_leds_fixos()`` a partir da
    própria classe. O salvamento-base histórico recria cada ROI somente com
    id/centro/raio e, por isso, um segmento desenhado ponto a ponto pode chegar
    ao JSON como círculo. Este patch fica exatamente nesse limite: deixa o fluxo
    legado executar normalmente e, em seguida, reafirma no projeto a geometria
    que estava visível no editor antes do salvamento.
    """
    import src.platform.led_project_manager as manager

    cls = manager.LedProjectManagerMixin
    if getattr(cls, "_odin_freeform_project_roundtrip", False):
        return

    original = cls._salvar_leds_no_projeto

    def salvar_leds_no_projeto_segmento_livre(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        geometria_editor = [
            copiar_mascara_absoluta_segmento_livre(led)
            for led in (getattr(self, "leds_selecionados", ()) or ())
        ]
        salvo = original(
            self,
            nome_projeto,
            parent=parent,
            confirmar_substituicao=confirmar_substituicao,
        )
        if not salvo or not geometria_editor:
            return bool(salvo)

        # Não reescreve projetos que contêm apenas círculos; o objetivo deste
        # guard é exclusivamente impedir a degradação de segmentos.
        if not any(
            normalizar_tipo_roi(getattr(led, "tipo_roi", None))
            == TIPO_ROI_SEGMENTO
            for led in geometria_editor
        ):
            return True

        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)
        if largura > 0 and altura > 0:
            geometria_editor = [
                led.com_normalizacao(
                    largura_base=largura,
                    altura_base=altura,
                )
                for led in geometria_editor
            ]

        repository = getattr(self, "config_repository", None)
        salvar = getattr(repository, "salvar_leds_fixos", None)
        if not callable(salvar):
            return True

        try:
            salvar(
                geometria_editor,
                largura_base=None,
                altura_base=None,
                projeto=nome_projeto,
            )
        except TypeError:
            try:
                salvar(geometria_editor, projeto=nome_projeto)
            except TypeError:
                salvar(geometria_editor)

        # O estado em memória deve representar exatamente o que acabou de ser
        # persistido, evitando que o círculo criado pelo fallback-base permaneça
        # visível até a próxima leitura do repositório.
        self.leds_fixos_configurados = [
            copiar_mascara_absoluta_segmento_livre(led)
            for led in geometria_editor
        ]
        self.leds_selecionados = [
            copiar_mascara_absoluta_segmento_livre(led)
            for led in geometria_editor
        ]
        return True

    cls._salvar_leds_no_projeto = salvar_leds_no_projeto_segmento_livre
    cls._odin_freeform_project_roundtrip = True


def instalar_persistencia_segmento_livre() -> None:
    global _PATCH_SEGMENTO_LIVRE_PERSISTENCIA
    if _PATCH_SEGMENTO_LIVRE_PERSISTENCIA:
        return

    import src.platform.fixed_mask_geometry_guard as fixed_guard
    import src.platform.segment_project_geometry_persistence as persistence
    from src.platform.mask_resolution_legacy_reference import (
        instalar_referencia_resolucao_mascaras_legadas,
    )

    fixed_guard.copiar_mascara_absoluta = copiar_mascara_absoluta_segmento_livre
    fixed_guard.assinatura_geometria = assinatura_geometria_segmento_livre
    persistence.copiar_led_geometria_completa = copiar_led_geometria_completa_segmento_livre
    _instalar_roundtrip_projeto_segmento_livre()
    instalar_referencia_resolucao_mascaras_legadas()
    _PATCH_SEGMENTO_LIVRE_PERSISTENCIA = True
