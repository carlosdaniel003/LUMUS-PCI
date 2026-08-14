"""Integrações cooperativas específicas do perfil ODIN display."""


def _instalar_persistencia_segmento_livre_global() -> None:
    # Instala antes que consumidores façam `from fixed_mask_geometry_guard import ...`.
    # Assim qualquer referência importada para o helper já preserva os vértices
    # livres, independentemente da ordem em que a aplicação/teste importe módulos.
    from src.platform.freeform_segment_persistence import (
        instalar_persistencia_segmento_livre,
    )

    instalar_persistencia_segmento_livre()


def _instalar_selecao_massa_no_editor() -> None:
    from src.platform import freeform_segment_roi
    from src.platform.mass_roi_selection_tool import MassRoiSelectionToolMixin

    atual = freeform_segment_roi.FreeformSegmentDrawingMixin
    if MassRoiSelectionToolMixin in getattr(atual, "__mro__", ()):
        return

    class FreeformSegmentDrawingComSelecaoMassa(
        atual,
        MassRoiSelectionToolMixin,
    ):
        pass

    FreeformSegmentDrawingComSelecaoMassa.__name__ = "FreeformSegmentDrawingMixin"
    FreeformSegmentDrawingComSelecaoMassa.__qualname__ = "FreeformSegmentDrawingMixin"
    FreeformSegmentDrawingComSelecaoMassa._odin_freeform_original_class = atual
    freeform_segment_roi.FreeformSegmentDrawingMixin = (
        FreeformSegmentDrawingComSelecaoMassa
    )


def _instalar_estado_persistente_toolbar_roi() -> None:
    from src.platform.roi_toolbar_theme import (
        instalar_preservacao_estado_toolbar_roi,
    )

    instalar_preservacao_estado_toolbar_roi()


def _instalar_toolbar_responsiva_selecao_led() -> None:
    from src.platform.responsive_led_selection_toolbar import (
        instalar_toolbar_selecao_led_responsiva,
    )

    instalar_toolbar_selecao_led_responsiva()


_instalar_persistencia_segmento_livre_global()
_instalar_selecao_massa_no_editor()
_instalar_estado_persistente_toolbar_roi()
_instalar_toolbar_responsiva_selecao_led()
