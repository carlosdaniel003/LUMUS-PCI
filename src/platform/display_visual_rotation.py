from __future__ import annotations

from copy import deepcopy

from src.core.roi_geometry import normalizar_angulo_segmento
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    converter_ponto_original_para_visual,
    dimensoes_visuais,
    normalizar_rotacao_visual,
    rotacionar_imagem_visual,
)


def obter_rotacao_visual_display(view) -> int:
    """Lê a orientação visual atual da tela principal sem alterar a câmera."""
    return normalizar_rotacao_visual(
        getattr(view, "rotacao_visual_principal", 0)
    )


def obter_rotacao_visual_do_frame_provider(frame_provider) -> int:
    """Resolve a rotação visual a partir do callback pertencente ao app F3."""
    app = getattr(frame_provider, "__self__", None)
    view = getattr(app, "view", None)
    return obter_rotacao_visual_display(view)


def preparar_frame_visual_display(frame, rotacao: int):
    """Retorna somente a representação visual usada pelo F3.

    O frame de origem nunca é modificado. A rotação segue exatamente a mesma
    convenção da imagem principal do ODIN (0/90/180/270 graus).
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame
    return rotacionar_imagem_visual(
        frame,
        normalizar_rotacao_visual(rotacao),
    )


def _ponto_visual(
    x: float,
    y: float,
    largura_original: int,
    altura_original: int,
    rotacao: int,
) -> list[int]:
    visual_x, visual_y = converter_ponto_original_para_visual(
        x,
        y,
        largura_original,
        altura_original,
        rotacao,
    )
    return [int(round(visual_x)), int(round(visual_y))]


def preparar_mascara_visual_display(
    mascara: dict,
    largura_original: int,
    altura_original: int,
    rotacao: int,
) -> dict:
    """Cria uma cópia visual da máscara sem alterar a geometria persistida."""
    item = deepcopy(mascara)
    angulo = normalizar_rotacao_visual(rotacao)
    if angulo == 0:
        return item

    tipo = str(item.get("type", "")).lower()
    mascara_id = str(item.get("id", ""))

    if tipo == "circle":
        cx, cy = _ponto_visual(
            item.get("cx", 0),
            item.get("cy", 0),
            largura_original,
            altura_original,
            angulo,
        )
        item["cx"] = cx
        item["cy"] = cy
        return item

    if tipo == "segment":
        cx, cy = _ponto_visual(
            item.get("cx", 0),
            item.get("cy", 0),
            largura_original,
            altura_original,
            angulo,
        )
        item["cx"] = cx
        item["cy"] = cy
        item["angle"] = normalizar_angulo_segmento(
            float(item.get("angle", 0) or 0) + angulo
        )
        return item

    if tipo == "polygon":
        item["points"] = [
            _ponto_visual(
                ponto[0],
                ponto[1],
                largura_original,
                altura_original,
                angulo,
            )
            for ponto in item.get("points", [])
            if isinstance(ponto, (list, tuple)) and len(ponto) >= 2
        ]
        return item

    if tipo == "rectangle":
        x = float(item.get("x", 0))
        y = float(item.get("y", 0))
        largura = float(item.get("width", 0))
        altura = float(item.get("height", 0))
        pontos = (
            (x, y),
            (x + largura, y),
            (x + largura, y + altura),
            (x, y + altura),
        )
        return {
            "id": mascara_id,
            "type": "polygon",
            "points": [
                _ponto_visual(
                    px,
                    py,
                    largura_original,
                    altura_original,
                    angulo,
                )
                for px, py in pontos
            ],
        }

    return item


def preparar_check_visual_display(
    frame,
    master_resolution,
    masks,
    rotacao: int,
):
    """Prepara frame, resolução e máscaras do CHECK na mesma orientação visual."""
    largura = max(1, int(master_resolution[0]))
    altura = max(1, int(master_resolution[1]))
    angulo = normalizar_rotacao_visual(rotacao)
    largura_visual, altura_visual = dimensoes_visuais(
        largura,
        altura,
        angulo,
    )
    frame_visual = preparar_frame_visual_display(frame, angulo)
    mascaras_visuais = [
        preparar_mascara_visual_display(
            mascara,
            largura,
            altura,
            angulo,
        )
        for mascara in (masks or [])
        if isinstance(mascara, dict)
    ]
    return (
        frame_visual,
        (largura_visual, altura_visual),
        mascaras_visuais,
    )


def instalar_rotacao_visual_editor_check_display() -> None:
    """Estende somente o gerenciador de CHECKS do F3 com rotação visual."""
    import src.platform.display_check_editor as check_module

    manager = check_module.DisplayCheckManagerWindow
    if getattr(manager, "_odin_display_check_visual_rotation", False):
        return

    def edit_selected(self) -> None:
        check_id = self._selected_id()
        if not check_id:
            return
        project = self.repository.carregar_projeto(self.project_name)
        check = self.repository.carregar_check(self.project_name, check_id)
        if project is None or check is None:
            return
        masks = project.get("masks", [])
        if not masks:
            check_module.messagebox.showwarning(
                "Sem máscaras",
                "Crie as máscaras do Projeto Display antes de editar os CHECKS.",
                parent=self.window,
            )
            return
        resolution = check_module.normalizar_resolucao_display(
            project.get("master_resolution")
        )
        if resolution is None:
            check_module.messagebox.showwarning(
                "Sem resolução mestre",
                "Defina a resolução mestre do Projeto Display primeiro.",
                parent=self.window,
            )
            return
        try:
            frame = self.frame_provider()
        except Exception:
            frame = None

        visual_rotation = obter_rotacao_visual_do_frame_provider(
            self.frame_provider
        )
        frame_visual, resolution_visual, masks_visual = (
            preparar_check_visual_display(
                frame,
                resolution,
                masks,
                visual_rotation,
            )
        )

        def save_states(states: dict[str, str]) -> None:
            if self.repository.salvar_estados_check(
                self.project_name,
                check_id,
                states,
            ):
                self.refresh(check_id)
                self._notify_change()

        self.check_editor = check_module.DisplayCheckMaskEditorWindow(
            root=self.root,
            project_name=self.project_name,
            check=check,
            master_resolution=resolution_visual,
            masks=masks_visual,
            frame=frame_visual,
            on_save=save_states,
        )
        try:
            self.check_editor.visual_rotation = visual_rotation
        except Exception:
            pass

    manager.edit_selected = edit_selected
    manager._odin_display_check_visual_rotation = True


instalar_rotacao_visual_editor_check_display()
