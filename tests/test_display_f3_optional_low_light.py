from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.models.led_features import LedFeatures
from src.platform.display_auto_check_analyzer import (
    DISPLAY_AUTO_CLASS_LOW_LIGHT,
    DisplayAutomaticCheckAnalyzer,
    DisplayLearnedStateClassifier,
)


def _features(value: float) -> LedFeatures:
    return LedFeatures(
        v_mean=float(value),
        v_max=float(value),
        v_p95=float(value),
        v_p99=float(value),
        glow_score=float(value),
    )


class DisplayF3OptionalLowLightTests(unittest.TestCase):
    def test_binary_classifier_works_without_low_light_reference(self):
        classifier = DisplayLearnedStateClassifier(
            learned_on=_features(220),
            learned_off=_features(20),
        )
        on_result = classifier.classify(_features(218))
        off_result = classifier.classify(_features(18))

        self.assertEqual("on", on_result.state)
        self.assertEqual("off", off_result.state)
        self.assertNotIn(DISPLAY_AUTO_CLASS_LOW_LIGHT, on_result.distances)
        self.assertNotIn(DISPLAY_AUTO_CLASS_LOW_LIGHT, off_result.distances)

    def test_analyzer_builds_classifier_with_on_and_off_only(self):
        with tempfile.TemporaryDirectory() as temp:
            analyzer = DisplayAutomaticCheckAnalyzer.__new__(
                DisplayAutomaticCheckAnalyzer
            )
            analyzer.repository = SimpleNamespace()
            learned = {
                "on": _features(220),
                "off": _features(20),
                "low_light": None,
            }
            analyzer.store = SimpleNamespace(
                config_file=Path(temp) / "learning.json",
                learned_features=lambda _project, state: learned[state],
            )
            analyzer._profile_cache_key = None
            analyzer._profile_cache = None

            classifier = analyzer._classifier_for_project("DISPLAY A")

            self.assertIsNotNone(classifier)
            result = classifier.classify(_features(218))
            self.assertEqual("on", result.state)
            self.assertNotIn(DISPLAY_AUTO_CLASS_LOW_LIGHT, result.distances)

    def test_low_light_is_added_automatically_when_learned(self):
        classifier = DisplayLearnedStateClassifier(
            learned_on=_features(220),
            learned_off=_features(20),
            learned_low_light=_features(90),
        )
        result = classifier.classify(_features(92))

        self.assertEqual(DISPLAY_AUTO_CLASS_LOW_LIGHT, result.state)
        self.assertIn(DISPLAY_AUTO_CLASS_LOW_LIGHT, result.distances)


if __name__ == "__main__":
    unittest.main()
