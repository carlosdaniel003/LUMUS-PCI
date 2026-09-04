from __future__ import annotations

"""Corrige o OK do editor de uma única máscara de referência do Display F3.

O editor visual trabalha nativamente com ``segment``. O fluxo legado de
referências passava a lista por ``normalizar_mascaras_display``, que pode remover
esse formato antes da validação e produzir o aviso "Uma máscara necessária"
mesmo com a ROI visível na tela.

A correção fica restrita ao editor de referência F3 e preserva exatamente a
geometria desenhada: segmento, círculo ou polígono.
"""

from copy import deepcopy
from tkinter import messagebox

from src.platform.display_mask_geometry import converter_mascara_legada_para_editor
from src.platform.display_reference_learning import DisplayReferenceMaskEditorWindow


def normalizar_mascara_referencia_editor_f3(mask: dict | None) -> dict | None:
    if not isinstance(mask, dict):
        return None

    try:
        item = converter_mascara_legada_para_editor(deepcopy(mask))
    except Exception:
        return None

    mask_id = str(item.get("id") or "DISPLAY_REFERENCE").strip() or "DISPLAY_REFERENCE"
    kind = str(item.get("type") or "").strip().lower()

    try:
        if kind == "segment":
            width = int(item.get("width"))
            height = int(item.get("height"))
            if width < 1 or height < 1:
                return None
            return {
                "id": mask_id,
                "type": "segment",
                "cx": int(item.get("cx")),
                "cy": int(item.get("cy")),
                "width": width,
                "height": height,
                "angle": float(item.get("angle", 0.0) or 0.0),
            }

        if kind == "circle":
            radius = int(item.get("radius"))
            if radius < 1:
                return None
            return {
                "id": mask_id,
                "type": "circle",
                "cx": int(item.get("cx")),
                "cy": int(item.get("cy")),
                "radius": radius,
            }

        if kind == "polygon":
            points = []
            for point in item.get("points", []) or []:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    return None
                points.append([int(round(float(point[0]))), int(round(float(point[1])))])
            if len(points) < 3:
                return None
            return {
                "id": mask_id,
                "type": "polygon",
                "points": points,
            }
    except (TypeError, ValueError):
        return None

    return None


def _save_reference_mask(self) -> None:
    if getattr(self, "freeform", None):
        self._finish_freeform()

    raw_masks = list(getattr(self, "masks", []) or [])
    masks = [
        normalized
        for normalized in (
            normalizar_mascara_referencia_editor_f3(mask)
            for mask in raw_masks
        )
        if normalized is not None
    ]

    if len(raw_masks) != 1 or len(masks) != 1:
        messagebox.showwarning(
            "Uma máscara necessária",
            "Desenhe exatamente uma máscara de referência antes de clicar em OK.",
            parent=self.window,
        )
        return

    if self.on_save:
        self.on_save(masks)
    self.close()


_INSTALLED = False


def instalar_correcao_salvamento_mascara_referencia_display_f3() -> None:
    """Troca somente o salvamento do editor de referência, sem tocar no F2."""
    global _INSTALLED
    if _INSTALLED:
        return

    DisplayReferenceMaskEditorWindow.save = _save_reference_mask
    DisplayReferenceMaskEditorWindow._display_f3_reference_mask_save_fix = True
    _INSTALLED = True
