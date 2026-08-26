from __future__ import annotations

import inspect
import unittest

import numpy as np

import src.platform.display_f3_check_transition_guard as transition_module
from src.platform.display_f3_check_transition_guard import (
    F3_CHECK_TRANSITION_STABLE_FRAMES,
    avaliar_preferencia_transicao_referencias_f3,
    decidir_transicao_estavel_f3,
)
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp


class _FakeMatcher:
    @staticmethod
    def _reference_image(metadata):
        return metadata.get("image")

    @staticmethod
    def _score(_current, metadata):
        return float(metadata.get("score", 0.0))

    @staticmethod
    def _threshold(metadata):
        return float(metadata.get("threshold", 0.72))


class DisplayF3CheckTransitionGuardTests(unittest.TestCase):
    @staticmethod
    def _references():
        last = np.full((80, 120, 3), 35, dtype=np.uint8)
        current = last.copy()
        last[20:60, 18:48] = 220
        current[20:60, 72:102] = 220
        return last, current

    def test_blue_permanece_quando_frame_ainda_e_blue_mesmo_usb_passando_threshold(self):
        blue, usb = self._references()
        matcher = _FakeMatcher()
        evidence = avaliar_preferencia_transicao_referencias_f3(
            matcher,
            blue,
            {"image": blue, "score": 0.96, "threshold": 0.72},
            {"image": usb, "score": 0.93, "threshold": 0.72},
        )
        self.assertTrue(evidence["available"])
        self.assertEqual("difference_mask", evidence["mode"])
        self.assertFalse(evidence["current_preferred"])
        self.assertLess(evidence["last_error"], evidence["current_error"])

    def test_usb_so_e_preferido_quando_frame_realmente_muda_para_usb(self):
        blue, usb = self._references()
        matcher = _FakeMatcher()
        evidence = avaliar_preferencia_transicao_referencias_f3(
            matcher,
            usb,
            {"image": blue, "score": 0.90, "threshold": 0.72},
            {"image": usb, "score": 0.97, "threshold": 0.72},
        )
        self.assertTrue(evidence["current_preferred"])
        self.assertLess(evidence["current_error"], evidence["last_error"])

    def test_transicao_exige_frames_consecutivos_antes_de_promover(self):
        pending_id = ""
        pending_frames = 0
        for index in range(1, F3_CHECK_TRANSITION_STABLE_FRAMES + 1):
            transition = decidir_transicao_estavel_f3(
                current_check_id="CHECK_USB",
                preferred=True,
                pending_check_id=pending_id,
                pending_frames=pending_frames,
            )
            pending_id = transition["pending_check_id"]
            pending_frames = transition["pending_frames"]
            self.assertEqual(index, pending_frames)
            if index < F3_CHECK_TRANSITION_STABLE_FRAMES:
                self.assertFalse(transition["promote"])
            else:
                self.assertTrue(transition["promote"])

    def test_um_frame_incorreto_zera_confirmacao_da_transicao(self):
        transition = decidir_transicao_estavel_f3(
            current_check_id="CHECK_USB",
            preferred=True,
            pending_check_id="CHECK_USB",
            pending_frames=2,
        )
        self.assertEqual(3, transition["pending_frames"])
        reset = decidir_transicao_estavel_f3(
            current_check_id="CHECK_USB",
            preferred=False,
            pending_check_id=transition["pending_check_id"],
            pending_frames=transition["pending_frames"],
        )
        self.assertFalse(reset["promote"])
        self.assertEqual("", reset["pending_check_id"])
        self.assertEqual(0, reset["pending_frames"])

    def test_guard_mantem_ultimo_check_enquanto_proximo_nao_foi_confirmado(self):
        source = inspect.getsource(transition_module._install_transition_guard)
        self.assertIn("_hold_last_check_state", source)
        self.assertIn("current_preferred", source)
        self.assertIn("pending_frames", source)

    def test_perfil_final_instala_guard_depois_do_status_operacional(self):
        source = inspect.getsource(RaspberryPi3ProductionApp.__init__)
        operational = source.index("instalar_status_operacional_display_f3()")
        transition = source.index("instalar_guard_transicao_check_display_f3()")
        self.assertLess(operational, transition)


if __name__ == "__main__":
    unittest.main()
