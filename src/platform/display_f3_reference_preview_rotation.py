from __future__ import annotations

"""Rotação apenas visual das referências de presença do Display F3.

As imagens persistidas continuam no referencial original da câmera porque o
classificador físico opera nesse domínio. Preview e seleção de ROI seguem a
rotação da tela principal e convertem o retângulo de volta antes de persistir.
"""

from pathlib import Path

import cv2
import tkinter as tk

import src.platform.display_check_presence_reference as check_module
import src.platform.display_reference_roi as roi_module
import src.platform.display_visual_reference_status as visual_module
from src.platform.display_visual_rotation import (
    obter_rotacao_visual_do_frame_provider,
    preparar_frame_visual_display,
)
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    normalizar_rotacao_visual,
)


F3_REFERENCE_ROI_COLOR = roi_module.DISPLAY_REFERENCE_ROI_COLOR


def transformar_roi_referencia_visual_f3(roi, rotacao: int) -> dict | None:
    """Converte um ROI normalizado para a orientação visual solicitada."""
    normalized = roi_module.normalizar_roi_referencia(roi)
    if normalized is None:
        return None
    angle = normalizar_rotacao_visual(rotacao)
    x = float(normalized["x"])
    y = float(normalized["y"])
    width = float(normalized["width"])
    height = float(normalized["height"])

    if angle == 90:
        value = {
            "x": 1.0 - (y + height),
            "y": x,
            "width": height,
            "height": width,
        }
    elif angle == 180:
        value = {
            "x": 1.0 - (x + width),
            "y": 1.0 - (y + height),
            "width": width,
            "height": height,
        }
    elif angle == 270:
        value = {
            "x": y,
            "y": 1.0 - (x + width),
            "width": height,
            "height": width,
        }
    else:
        value = normalized
    return roi_module.normalizar_roi_referencia(value)


def restaurar_roi_referencia_original_f3(roi_visual, rotacao: int) -> dict | None:
    angle = normalizar_rotacao_visual(rotacao)
    return transformar_roi_referencia_visual_f3(
        roi_visual,
        (360 - angle) % 360,
    )


def _rotation(owner) -> int:
    provider = getattr(owner, "frame_provider", None)
    if provider is None:
        return 0
    try:
        return obter_rotacao_visual_do_frame_provider(provider)
    except Exception:
        return 0


def preparar_preview_referencia_visual_f3(image, rotacao: int):
    if image is None or getattr(image, "size", 0) == 0:
        return image
    return preparar_frame_visual_display(
        image,
        normalizar_rotacao_visual(rotacao),
    )


def _draw_roi_on_canvas(
    canvas,
    image_visual,
    roi_visual,
    *,
    target_width: int,
    target_height: int,
    center_x: float,
    center_y: float,
) -> None:
    if canvas is None or roi_visual is None:
        return
    rect = roi_module._canvas_roi_rect(
        image_visual,
        roi_visual,
        target_width,
        target_height,
        center_x,
        center_y,
    )
    if rect is None:
        return
    canvas.create_rectangle(
        *rect,
        outline=F3_REFERENCE_ROI_COLOR,
        width=2,
    )


def _install_project_reference_preview() -> None:
    cls = visual_module.DisplayProjectConfigPresenceWindow
    if bool(getattr(cls, "_display_f3_reference_preview_rotation", False)):
        return

    def update_detail(self) -> None:
        store = getattr(self, "_project_presence_store", None)
        if store is None:
            return
        project_name = self._selected_name()
        angle = _rotation(self)
        self._project_presence_photos.clear()
        labels = getattr(self, "_project_presence_roi_labels", {})

        for kind in visual_module.DISPLAY_PROJECT_REFERENCE_TYPES:
            canvas = self._project_presence_canvases.get(kind)
            status = self._project_presence_status.get(kind)
            roi_label = labels.get(kind)
            if canvas is None or status is None:
                continue
            canvas.delete("all")
            metadata = store.get(project_name or "", kind) if project_name else None
            if metadata is None:
                canvas.create_text(
                    87,
                    41,
                    text="SEM FOTO",
                    fill="#64748B",
                    font=("Segoe UI", 8, "bold"),
                )
                status.configure(text="SEM REFERÊNCIA", fg=self.MUTED)
                if roi_label is not None:
                    roi_label.configure(text="IMAGEM TODA", fg="#94A3B8")
                continue

            path = Path(str(metadata.get("image_path") or ""))
            image_raw = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.exists() else None
            if image_raw is None:
                canvas.create_text(
                    87,
                    41,
                    text="ARQUIVO AUSENTE",
                    fill="#FCA5A5",
                    font=("Segoe UI", 7, "bold"),
                )
                status.configure(text="ARQUIVO AUSENTE", fg="#FCA5A5")
                continue

            image_visual = preparar_preview_referencia_visual_f3(image_raw, angle)
            photo = visual_module._photo_from_image(image_visual, 170, 78)
            if photo is not None:
                self._project_presence_photos[kind] = photo
                canvas.create_image(87, 41, image=photo, anchor=tk.CENTER)

            roi_raw = roi_module.normalizar_roi_referencia(metadata.get("roi"))
            roi_visual = transformar_roi_referencia_visual_f3(roi_raw, angle)
            _draw_roi_on_canvas(
                canvas,
                image_visual,
                roi_visual,
                target_width=170,
                target_height=78,
                center_x=87,
                center_y=41,
            )
            if roi_label is not None:
                roi_label.configure(
                    text=roi_module.descricao_roi_referencia(metadata),
                    fg=F3_REFERENCE_ROI_COLOR if roi_raw is not None else "#94A3B8",
                )
            status.configure(
                text=(
                    f"ATIVA • {int(metadata.get('width', 0))}x"
                    f"{int(metadata.get('height', 0))} • VISUAL {angle}°"
                ),
                fg="#86EFAC",
            )

    def select_roi(self, kind: str) -> None:
        store = getattr(self, "_project_presence_store", None)
        project_name = self._selected_name()
        if store is None or not project_name:
            return
        metadata = store.get(project_name, kind)
        if metadata is None:
            visual_module.messagebox.showwarning(
                "Sem referência",
                "Capture primeiro esta foto de presença da placa.",
                parent=self.window,
            )
            return
        path = Path(str(metadata.get("image_path") or ""))
        image_raw = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.exists() else None
        if image_raw is None:
            visual_module.messagebox.showwarning(
                "Sem imagem de referência",
                "A imagem de referência não foi encontrada.",
                parent=self.window,
            )
            return

        angle = _rotation(self)
        image_visual = preparar_preview_referencia_visual_f3(image_raw, angle)
        roi_visual = transformar_roi_referencia_visual_f3(metadata.get("roi"), angle)

        def apply(visual_roi):
            raw_roi = restaurar_roi_referencia_original_f3(visual_roi, angle)
            store.set_roi(project_name, kind, raw_roi)
            self._update_project_presence_detail()
            self._notify_change()
            self.status.configure(
                text=(
                    f"Área analisada de '"
                    f"{visual_module.DISPLAY_PROJECT_REFERENCE_LABELS[kind]}' atualizada."
                )
            )

        roi_module.DisplayReferenceRoiDialog(
            self.window,
            image_visual,
            roi_visual,
            apply,
            f"Área analisada • {visual_module.DISPLAY_PROJECT_REFERENCE_LABELS[kind]}",
        )

    cls._update_project_presence_detail = update_detail
    cls.select_project_presence_reference_roi = select_roi
    cls._display_f3_reference_preview_rotation = True


def _install_check_reference_preview() -> None:
    cls = check_module.DisplayCheckManagerPresenceWindow
    if bool(getattr(cls, "_display_f3_reference_preview_rotation", False)):
        return

    def update_detail(self) -> None:
        canvas = getattr(self, "reference_canvas", None)
        status = getattr(self, "reference_status", None)
        store = getattr(self, "_presence_store", None)
        if canvas is None or status is None or store is None:
            return
        canvas.delete("all")
        self._presence_photo = None
        check_id = self._selected_id()
        if not check_id:
            status.configure(text="Selecione um CHECK.", fg=self.MUTED)
            return

        metadata = store.get(self.project_name, check_id)
        if metadata is None:
            status.configure(text="Nenhuma referência visual anexada.", fg=self.MUTED)
            canvas.create_text(
                165,
                46,
                text="SEM REFERÊNCIA",
                fill="#64748B",
                font=("Segoe UI", 9, "bold"),
            )
            label = getattr(self, "reference_roi_status", None)
            if label is not None:
                label.configure(text="IMAGEM TODA", fg="#94A3B8")
            return

        path = Path(str(metadata.get("image_path") or ""))
        image_raw = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.exists() else None
        if image_raw is None:
            status.configure(
                text="Referência configurada, mas o arquivo de imagem não foi encontrado.",
                fg="#FCA5A5",
            )
            canvas.create_text(
                165,
                46,
                text="ARQUIVO AUSENTE",
                fill="#FCA5A5",
                font=("Segoe UI", 9, "bold"),
            )
            return

        angle = _rotation(self)
        image_visual = preparar_preview_referencia_visual_f3(image_raw, angle)
        photo = self._photo_from_image(image_visual, 326, 88)
        if photo is not None:
            self._presence_photo = photo
            canvas.create_image(165, 46, image=photo, anchor=tk.CENTER)

        roi_raw = roi_module.normalizar_roi_referencia(metadata.get("roi"))
        roi_visual = transformar_roi_referencia_visual_f3(roi_raw, angle)
        _draw_roi_on_canvas(
            canvas,
            image_visual,
            roi_visual,
            target_width=326,
            target_height=88,
            center_x=165,
            center_y=46,
        )
        label = getattr(self, "reference_roi_status", None)
        if label is not None:
            label.configure(
                text=roi_module.descricao_roi_referencia(metadata),
                fg=F3_REFERENCE_ROI_COLOR if roi_raw is not None else "#94A3B8",
            )
        threshold = float(
            metadata.get(
                "threshold",
                check_module.DISPLAY_CHECK_PRESENCE_DEFAULT_THRESHOLD,
            )
        )
        status.configure(
            text=(
                f"Referência ativa • mínimo {threshold * 100:.0f}% • "
                f"{int(metadata.get('width', 0))}x{int(metadata.get('height', 0))} • "
                f"VISUAL {angle}°"
            ),
            fg="#86EFAC",
        )

    def select_roi(self) -> None:
        store = getattr(self, "_presence_store", None)
        check_id = self._selected_id()
        if store is None or not check_id:
            return
        metadata = store.get(self.project_name, check_id)
        if metadata is None:
            check_module.messagebox.showwarning(
                "Sem referência",
                "Capture primeiro a foto deste CHECK.",
                parent=self.window,
            )
            return
        path = Path(str(metadata.get("image_path") or ""))
        image_raw = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.exists() else None
        if image_raw is None:
            check_module.messagebox.showwarning(
                "Sem imagem de referência",
                "A imagem de referência não foi encontrada.",
                parent=self.window,
            )
            return

        angle = _rotation(self)
        image_visual = preparar_preview_referencia_visual_f3(image_raw, angle)
        roi_visual = transformar_roi_referencia_visual_f3(metadata.get("roi"), angle)

        def apply(visual_roi):
            raw_roi = restaurar_roi_referencia_original_f3(visual_roi, angle)
            store.set_roi(self.project_name, check_id, raw_roi)
            self._update_presence_detail()
            self._notify_change()
            self.status.configure(text="Área da referência visual atualizada.")

        roi_module.DisplayReferenceRoiDialog(
            self.window,
            image_visual,
            roi_visual,
            apply,
            f"Área analisada • {check_id}",
        )

    cls._update_presence_detail = update_detail
    cls.select_presence_reference_roi = select_roi
    cls._display_f3_reference_preview_rotation = True


def instalar_rotacao_preview_referencias_display_f3() -> None:
    _install_project_reference_preview()
    _install_check_reference_preview()
