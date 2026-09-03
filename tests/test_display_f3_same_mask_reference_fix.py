from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import numpy as np

import src.platform.display_f3_same_mask_reference_fix as same_mask_module
from src.models.led_features import LedFeatures
from src.platform.display_check_presence_reference import (
    DisplayCheckPresenceReferenceStore,
)
from src.platform.display_f3_reference_authority_fix import (
    F3_REFERENCE_MIN_CONFIDENCE,
)
from src.platform.display_f3_same_mask_reference_fix import (
    F3_STATE_SAMPLE_FALLBACK_SOURCE,
    F3SameMaskReferenceAnalyzer,
    classificar_mascara_por_referencias_locais_f3,
)
from src.platform.display_project_repository import DisplayProjectRepository


def _features(value: float) -> LedFeatures:
    return LedFeatures(
        v_mean=float(value),
        v_max=float(value),
        v_std=float(value) * 0.18,
        v_p95=float(value),
        v_p99=float(value),
        s_mean=float(value) * 0.22,
        s_std=float(value) * 0.08,
        center_to_ring_v=float(value) * 0.06,
        center_to_ring_s=float(value) * 0.02,
        percent_hot_235=max(0.0, min(1.0, (float(value) - 180.0) / 80.0)),
        percent_hot_245=max(0.0, min(1.0, (float(value) - 200.0) / 60.0)),
        percent_hot_250=max(0.0, min(1.0, (float(value) - 220.0) / 40.0)),
        glow_score=float(value) * 0.20,
        area_pixels=120,
        inner_area_pixels=60,
        ring_area_pixels=60,
    )


class DisplayF3SameMaskReferenceFixTests(unittest.TestCase):
    def test_reflexo_legitimo_off_is_compared_with_same_physical_mask(self):
        result = classificar_mascara_por_referencias_locais_f3(
            current=_features(121),
            on_references=[_features(220)],
            off_references=[_features(120)],
            low_light_references=[],
        )

        self.assertIsNotNone(result)
        self.assertEqual("off", result["state"])
        self.assertEqual("f3_same_mask_checks", result["reference_source"])
        self.assertGreaterEqual(result["confidence"], F3_REFERENCE_MIN_CONFIDENCE)
        self.assertLess(result["distances"]["off"], result["distances"]["on"])

    def test_same_mask_classifier_does_not_receive_expected_state(self):
        result = classificar_mascara_por_referencias_locais_f3(
            current=_features(219),
            on_references=[_features(220)],
            off_references=[_features(120)],
            low_light_references=[],
        )

        self.assertIsNotNone(result)
        self.assertEqual("on", result["state"])

    def test_near_tie_keeps_searching_by_low_confidence(self):
        result = classificar_mascara_por_referencias_locais_f3(
            current=_features(150),
            on_references=[_features(160)],
            off_references=[_features(140)],
            low_light_references=[],
        )

        self.assertIsNotNone(result)
        self.assertLess(result["confidence"], F3_REFERENCE_MIN_CONFIDENCE)

    def test_profiles_are_built_from_same_mask_across_check_photos(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = DisplayProjectRepository(root / "odin_display_projects.json")
            self.assertTrue(repository.adicionar_projeto("DISPLAY A", (120, 80)))
            mask = {
                "id": "MASK_001",
                "type": "circle",
                "cx": 60,
                "cy": 40,
                "radius": 10,
            }
            self.assertTrue(repository.salvar_mascaras("DISPLAY A", [mask]))

            checks = repository.listar_checks("DISPLAY A")
            self.assertGreaterEqual(len(checks), 2)
            on_check_id = str(checks[0]["id"])
            off_check_id = str(checks[1]["id"])
            self.assertTrue(
                repository.salvar_estados_check(
                    "DISPLAY A",
                    on_check_id,
                    {"MASK_001": "on"},
                )
            )
            self.assertTrue(
                repository.salvar_estados_check(
                    "DISPLAY A",
                    off_check_id,
                    {"MASK_001": "off"},
                )
            )

            presence_store = DisplayCheckPresenceReferenceStore(repository)
            on_frame = np.full((80, 120, 3), 220, dtype=np.uint8)
            off_frame = np.full((80, 120, 3), 120, dtype=np.uint8)
            self.assertIsNotNone(
                presence_store.capture(
                    "DISPLAY A",
                    on_check_id,
                    on_frame,
                    (120, 80),
                )
            )
            self.assertIsNotNone(
                presence_store.capture(
                    "DISPLAY A",
                    off_check_id,
                    off_frame,
                    (120, 80),
                )
            )

            analyzer = F3SameMaskReferenceAnalyzer(repository)
            project = repository.carregar_projeto("DISPLAY A")
            profiles = analyzer._build_same_mask_profiles(
                "DISPLAY A",
                project,
                list(project.get("masks", [])),
                0,
            )

            profile = profiles["MASK_001"]
            self.assertEqual(1, len(profile["on"]))
            self.assertEqual(1, len(profile["off"]))
            self.assertEqual(
                on_check_id,
                profile["sources"]["on"][0]["check_id"],
            )
            self.assertEqual(
                off_check_id,
                profile["sources"]["off"][0]["check_id"],
            )

    def test_missing_local_pair_falls_back_without_current_check_photo(self):
        source = inspect.getsource(F3SameMaskReferenceAnalyzer.analyze)
        self.assertIn("check_expected_reference=None", source)
        self.assertIn("F3_STATE_SAMPLE_FALLBACK_SOURCE", source)
        self.assertEqual(
            "f3_state_samples_no_check_photo",
            F3_STATE_SAMPLE_FALLBACK_SOURCE,
        )

    def test_module_isolated_from_other_production_mode(self):
        source = inspect.getsource(same_mask_module)
        for forbidden in (
            "src.platform.f2_",
            "F2Automatic",
            "operacao_engine",
            "linux_f2_fixed_resolution",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
