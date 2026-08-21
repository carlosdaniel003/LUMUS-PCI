from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

import src.platform.display_check_editor as check_module
from src.platform.display_visual_rotation import (
    obter_rotacao_visual_do_frame_provider,
    preparar_check_visual_display,
)


class _FrameOwner:
    def __init__(self, rotation: int, frame) -> None:
        self.view = SimpleNamespace(rotacao_visual_principal=rotation)
        self._frame = frame

    def frame_provider(self):
        return self._frame.copy()


class _Repository:
    def __init__(self, project: dict, check: dict) -> None:
        self.project = deepcopy(project)
        self.check = deepcopy(check)
        self.saved_states = None

    def carregar_projeto(self, _name):
        return deepcopy(self.project)

    def carregar_check(self, _project_name, _check_id):
        return deepcopy(self.check)

    def salvar_estados_check(self, _project_name, _check_id, states):
        self.saved_states = deepcopy(states)
        return True


class DisplayCheckVisualRotationTests(unittest.TestCase):
    def test_check_visual_rotates_frame_resolution_and_masks_together(self):
        frame = np.arange(2 * 3 * 3, dtype=np.uint8).reshape((2, 3, 3))
        masks = [
            {"id": "MASK_001", "type": "circle", "cx": 0, "cy": 0, "radius": 1},
            {
                "id": "MASK_002",
                "type": "segment",
                "cx": 2,
                "cy": 1,
                "width": 10,
                "height": 4,
                "angle": 0.0,
            },
            {
                "id": "MASK_003",
                "type": "polygon",
                "points": [[0, 0], [2, 0], [2, 1]],
            },
            {
                "id": "MASK_004",
                "type": "rectangle",
                "x": 0,
                "y": 0,
                "width": 2,
                "height": 1,
            },
        ]
        frame_before = frame.copy()
        masks_before = deepcopy(masks)

        visual_frame, visual_resolution, visual_masks = preparar_check_visual_display(
            frame,
            (3, 2),
            masks,
            90,
        )

        self.assertEqual((2, 3), visual_resolution)
        self.assertEqual((3, 2, 3), visual_frame.shape)
        self.assertTrue(np.array_equal(frame, frame_before))
        self.assertEqual(masks_before, masks)

        self.assertEqual((1, 0), (visual_masks[0]["cx"], visual_masks[0]["cy"]))
        self.assertEqual((0, 2), (visual_masks[1]["cx"], visual_masks[1]["cy"]))
        self.assertAlmostEqual(90.0, float(visual_masks[1]["angle"]))
        self.assertEqual("polygon", visual_masks[3]["type"])
        self.assertEqual(
            [mask["id"] for mask in masks],
            [mask["id"] for mask in visual_masks],
        )

    def test_rotation_is_resolved_from_f3_bound_frame_provider(self):
        owner = _FrameOwner(270, np.zeros((4, 6, 3), dtype=np.uint8))
        self.assertEqual(270, obter_rotacao_visual_do_frame_provider(owner.frame_provider))

    def test_manager_opens_check_editor_in_current_main_visual_rotation(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        owner = _FrameOwner(90, frame)
        project = {
            "name": "DISPLAY TESTE",
            "master_resolution": {"width": 640, "height": 480},
            "masks": [
                {
                    "id": "MASK_001",
                    "type": "circle",
                    "cx": 100,
                    "cy": 50,
                    "radius": 12,
                }
            ],
        }
        check = {
            "id": "CHECK_001",
            "name": "BLUE",
            "mask_states": {"MASK_001": "on"},
        }
        repository = _Repository(project, check)
        captured = {}

        class FakeEditor:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.visible = True

        original_editor = check_module.DisplayCheckMaskEditorWindow
        check_module.DisplayCheckMaskEditorWindow = FakeEditor
        try:
            manager = SimpleNamespace(
                project_name="DISPLAY TESTE",
                repository=repository,
                frame_provider=owner.frame_provider,
                root=object(),
                window=object(),
                check_editor=None,
                _selected_id=lambda: "CHECK_001",
                refresh=lambda _check_id=None: None,
                _notify_change=lambda: None,
            )
            check_module.DisplayCheckManagerWindow.edit_selected(manager)
        finally:
            check_module.DisplayCheckMaskEditorWindow = original_editor

        self.assertEqual((480, 640), tuple(captured["master_resolution"]))
        self.assertEqual((640, 480, 3), captured["frame"].shape)
        self.assertEqual("MASK_001", captured["masks"][0]["id"])
        self.assertEqual((429, 100), (captured["masks"][0]["cx"], captured["masks"][0]["cy"]))
        self.assertEqual(90, captured.get("visual_rotation", 90))

    def test_rotation_extension_does_not_reference_f2_runtime_state(self):
        source = Path("src/platform/display_visual_rotation.py").read_text(encoding="utf-8")
        for forbidden in (
            "operacao_engine",
            "operacao_ativa",
            "leds_selecionados",
            "leds_fixos_configurados",
            "linux_f2_fixed_resolution",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
