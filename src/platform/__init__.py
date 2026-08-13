"""Integrações cooperativas específicas do perfil ODIN display."""


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


_instalar_selecao_massa_no_editor()
