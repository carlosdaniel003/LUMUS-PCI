from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import cv2
from tkinter import messagebox

import src.platform.display_reference_learning as learning
from src.platform.display_project_repository import (
    normalizar_mascaras_display,
    normalizar_resolucao_display,
)
from src.platform.display_reference_store import (
    DISPLAY_REFERENCE_LABELS,
    DisplayReferenceLimitError,
)
from src.platform.display_visual_rotation import (
    obter_rotacao_visual_do_frame_provider,
    preparar_frame_visual_display,
)
from src.ui.main_window_parts.image.rotacao_visual_principal import dimensoes_visuais


def _save_editor(self):
    if self.freeform:
        self._finish_freeform()
    masks = normalizar_mascaras_display(deepcopy(self.masks))
    if len(masks) != 1:
        messagebox.showwarning(
            "Uma máscara necessária",
            "Desenhe exatamente uma máscara de referência antes de clicar em OK.",
            parent=self.window,
        )
        return
    result = True
    if self.on_save:
        result = self.on_save(masks)
    if result is False:
        return
    self.close()


def _save_reference(self, tipo, scope, index, frame, mask, existing):
    try:
        learned = learning.learn_display_reference(frame, mask)
        crop = learning.crop_display_reference(frame, mask)
        if crop is None or getattr(crop, "size", 0) == 0:
            raise ValueError("Não foi possível gerar o recorte da referência.")

        sample_id = str((existing or {}).get("id") or uuid4().hex)
        old_path = str((existing or {}).get("image_path") or "")
        if old_path:
            path = Path(old_path)
        else:
            destination = "global" if scope == "global" else learning._slug(self.project_name)
            path = learning.DISPLAY_REFERENCE_IMAGE_DIR / (
                f"reference_{destination}_{tipo}_{sample_id[:10]}.png"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), crop):
            raise RuntimeError("Não foi possível gravar a imagem da referência Display.")

        sample = {
            "id": sample_id,
            "image_path": str(path),
            "features": learned["features"],
            "mask": learned["mask"],
            "selection": learned["selection"],
        }
        self.store.save_sample(
            self.project_name,
            tipo,
            sample,
            scope=scope,
            index=index,
        )
    except (DisplayReferenceLimitError, ValueError, IndexError, RuntimeError) as error:
        messagebox.showwarning(
            "Referência não salva",
            str(error),
            parent=self.window,
        )
        return False

    self.refresh()
    self._notify_change()
    try:
        self.window.lift()
        self.window.focus_force()
    except Exception:
        pass
    return True


def _capture_reference(self, tipo: str, scope: str, index: int | None) -> None:
    project = self.repository.carregar_projeto(self.project_name)
    if project is None:
        return
    resolution = normalizar_resolucao_display(project.get("master_resolution"))
    if resolution is None:
        messagebox.showwarning(
            "Resolução necessária",
            "Defina a resolução mestre do Projeto Display primeiro.",
            parent=self.window,
        )
        return
    try:
        frame = self.frame_provider()
    except Exception:
        frame = None
    if frame is None or getattr(frame, "size", 0) == 0:
        messagebox.showwarning(
            "Câmera necessária",
            "Não existe um frame válido da câmera para capturar a referência.",
            parent=self.window,
        )
        return

    rotation = obter_rotacao_visual_do_frame_provider(self.frame_provider)
    frame_visual = preparar_frame_visual_display(frame, rotation)
    visual_resolution = dimensoes_visuais(resolution[0], resolution[1], rotation)
    expected_shape = (int(visual_resolution[1]), int(visual_resolution[0]))
    if tuple(frame_visual.shape[:2]) != expected_shape:
        frame_visual = cv2.resize(
            frame_visual,
            (int(visual_resolution[0]), int(visual_resolution[1])),
            interpolation=cv2.INTER_AREA,
        )

    existing = self._entry_sample(tipo, scope, index)
    initial_masks = (
        [deepcopy(existing["mask"])]
        if isinstance(existing, dict) and isinstance(existing.get("mask"), dict)
        else []
    )

    def save_mask(masks: list[dict]):
        return self._save_reference(
            tipo,
            scope,
            index,
            frame_visual,
            masks[0],
            existing,
        )

    self.capture_editor = learning.DisplayReferenceMaskEditorWindow(
        root=self.root,
        master_resolution=visual_resolution,
        masks=initial_masks,
        frame=frame_visual,
        on_save=save_mask,
        reference_label=(
            f"REFERÊNCIA {DISPLAY_REFERENCE_LABELS[tipo]} • "
            f"{'GLOBAL' if scope == 'global' else self.project_name}"
        ),
    )


def install_display_reference_learning_guard() -> None:
    if getattr(
        learning.DisplayReferenceMaskEditorWindow,
        "_odin_reference_guard",
        False,
    ):
        return
    learning.DisplayReferenceMaskEditorWindow.save = _save_editor
    learning.DisplayReferenceMaskEditorWindow._odin_reference_guard = True
    learning.DisplayReferenceConfigWindow._save_reference = _save_reference
    learning.DisplayReferenceConfigWindow.capture_reference = _capture_reference
    learning.DisplayReferenceConfigWindow._odin_reference_guard = True


install_display_reference_learning_guard()
