from __future__ import annotations

import inspect
import unittest

import cv2
import numpy as np

from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_KEY,
    F2_BOARD_PRESENCE_PRESENT,
    F2_BOARD_PRESENCE_UNAVAILABLE,
    F2_BOARD_REF_BOARD_OFF,
    F2_BOARD_REF_BOARD_ON,
    F2_BOARD_REF_EMPTY,
    F2BoardPresenceClassifier,
    definir_referencia_presenca_projeto,
    normalizar_referencias_presenca,
    obter_referencias_presenca_projeto,
)


class F2BoardPresenceReferenceTests(unittest.TestCase):
    @staticmethod
    def _scene(*, board: bool, leds_on: bool = False) -> np.ndarray:
        frame = np.full((480, 640, 3), 28, dtype=np.uint8)
        cv2.rectangle(frame, (90, 70), (550, 410), (45, 45, 45), -1)
        cv2.rectangle(frame, (110, 90), (530, 390), (65, 65, 65), 3)

        if board:
            cv2.rectangle(frame, (150, 110), (490, 370), (112, 112, 112), -1)
            cv2.rectangle(frame, (175, 135), (465, 345), (72, 72, 72), 4)
            cv2.line(frame, (180, 235), (460, 235), (160, 160, 160), 4)
            cv2.line(frame, (365, 140), (365, 340), (150, 150, 150), 4)
            level = 250 if leds_on else 58
            for x, y in ((220, 180), (320, 180), (220, 280), (320, 280)):
                cv2.circle(frame, (x, y), 9, (level, level, level), -1)
        return frame

    def test_three_references_distinguish_present_and_empty(self):
        classifier = F2BoardPresenceClassifier()
        self.assertTrue(
            classifier.configure(
                {
                    F2_BOARD_REF_BOARD_ON: self._scene(board=True, leds_on=True),
                    F2_BOARD_REF_BOARD_OFF: self._scene(board=True, leds_on=False),
                    F2_BOARD_REF_EMPTY: self._scene(board=False),
                }
            )
        )

        status_on, _ = classifier.classify(self._scene(board=True, leds_on=True))
        status_off, _ = classifier.classify(self._scene(board=True, leds_on=False))
        status_empty, _ = classifier.classify(self._scene(board=False))

        self.assertEqual(F2_BOARD_PRESENCE_PRESENT, status_on)
        self.assertEqual(F2_BOARD_PRESENCE_PRESENT, status_off)
        self.assertEqual(F2_BOARD_PRESENCE_EMPTY, status_empty)

    def test_led_state_change_does_not_mean_board_removed(self):
        classifier = F2BoardPresenceClassifier()
        classifier.configure(
            {
                F2_BOARD_REF_BOARD_ON: self._scene(board=True, leds_on=True),
                F2_BOARD_REF_BOARD_OFF: self._scene(board=True, leds_on=False),
                F2_BOARD_REF_EMPTY: self._scene(board=False),
            }
        )
        for leds_on in (True, False, True, False, False, True):
            status, _ = classifier.classify(
                self._scene(board=True, leds_on=leds_on)
            )
            self.assertEqual(F2_BOARD_PRESENCE_PRESENT, status)

    def test_classifier_is_unavailable_until_all_three_slots_exist(self):
        classifier = F2BoardPresenceClassifier()
        status, scores = classifier.classify(self._scene(board=True))
        self.assertEqual(F2_BOARD_PRESENCE_UNAVAILABLE, status)
        self.assertEqual({}, scores)

        self.assertFalse(
            classifier.configure(
                {
                    F2_BOARD_REF_BOARD_ON: self._scene(board=True, leds_on=True),
                    F2_BOARD_REF_BOARD_OFF: self._scene(board=True, leds_on=False),
                }
            )
        )
        self.assertFalse(classifier.ready)

    def test_references_are_stored_inside_selected_project(self):
        config = {
            "led_projects": {
                "PROJETO A": {"name": "PROJETO A", "fixed_leds": []},
                "PROJETO B": {"name": "PROJETO B", "fixed_leds": []},
            }
        }
        entry = {
            "image_path": "/tmp/board_on.png",
            "width": 640,
            "height": 480,
            "updated_at": "now",
        }
        updated = definir_referencia_presenca_projeto(
            config,
            "PROJETO A",
            F2_BOARD_REF_BOARD_ON,
            entry,
        )

        refs_a = obter_referencias_presenca_projeto(updated, "PROJETO A")
        refs_b = obter_referencias_presenca_projeto(updated, "PROJETO B")
        self.assertEqual("/tmp/board_on.png", refs_a[F2_BOARD_REF_BOARD_ON]["image_path"])
        self.assertEqual({}, refs_b[F2_BOARD_REF_BOARD_ON])
        self.assertIn(
            F2_BOARD_PRESENCE_KEY,
            updated["led_projects"]["PROJETO A"],
        )

    def test_removing_one_slot_keeps_other_project_references(self):
        refs = normalizar_referencias_presenca(
            {
                F2_BOARD_REF_BOARD_ON: {
                    "image_path": "on.png",
                    "width": 640,
                    "height": 480,
                },
                F2_BOARD_REF_BOARD_OFF: {
                    "image_path": "off.png",
                    "width": 640,
                    "height": 480,
                },
                F2_BOARD_REF_EMPTY: {
                    "image_path": "empty.png",
                    "width": 640,
                    "height": 480,
                },
            }
        )
        config = {
            "led_projects": {
                "P": {
                    "name": "P",
                    "fixed_leds": [],
                    F2_BOARD_PRESENCE_KEY: refs,
                }
            }
        }
        updated = definir_referencia_presenca_projeto(
            config,
            "P",
            F2_BOARD_REF_BOARD_OFF,
            None,
        )
        loaded = obter_referencias_presenca_projeto(updated, "P")
        self.assertTrue(loaded[F2_BOARD_REF_BOARD_ON])
        self.assertEqual({}, loaded[F2_BOARD_REF_BOARD_OFF])
        self.assertTrue(loaded[F2_BOARD_REF_EMPTY])

    def test_ui_explicitly_contains_three_full_frame_slots_and_project_link(self):
        import src.platform.f2_board_presence_references as module

        source = inspect.getsource(module)
        self.assertIn("1. Placa fixa ligada", source)
        self.assertIn("2. Placa fixa desligada", source)
        self.assertIn("3. Placa fora do suporte", source)
        self.assertIn("imagem completa", source.lower())
        self.assertIn("Projeto ativo", source)
        self.assertIn("F2 automático", source)


if __name__ == "__main__":
    unittest.main()
