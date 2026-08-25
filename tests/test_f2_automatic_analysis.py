from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection
from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.f2_automatic_analysis import (
    F2_AUTO_ANALYSIS_INTERVAL_S,
    F2_AUTO_SETTING_KEY,
    F2AutomaticTriggerLatch,
    carregar_analise_automatica_f2,
    salvar_analise_automatica_f2,
)
from src.platform.segment_display_operation_window import (
    F2_LIVE_ROI_OVERLAY_ALPHA,
    renderizar_overlay_rois_f2,
)


class F2AutomaticAnalysisTests(unittest.TestCase):
    def test_one_lit_roi_triggers_once(self):
        latch = F2AutomaticTriggerLatch()
        self.assertTrue(latch.observe({"LED_001": "ACESO"}, can_trigger=True))
        self.assertFalse(latch.observe({"LED_001": "ACESO"}, can_trigger=True))
        self.assertFalse(latch.armed)

    def test_low_light_is_visible_but_does_not_trigger_by_itself(self):
        latch = F2AutomaticTriggerLatch()
        self.assertFalse(
            latch.observe({"LED_001": "POUCA_LUZ"}, can_trigger=True)
        )
        self.assertTrue(latch.armed)
        self.assertTrue(
            latch.observe(
                {"LED_001": "POUCA_LUZ", "LED_002": "ACESO"},
                can_trigger=True,
            )
        )

    def test_same_board_rearms_only_after_two_all_off_frames(self):
        latch = F2AutomaticTriggerLatch(off_frames_required=2)
        self.assertTrue(latch.observe({"LED_001": "ACESO"}))
        self.assertFalse(latch.observe({"LED_001": "APAGADO"}))
        self.assertFalse(latch.armed)
        self.assertFalse(latch.observe({"LED_001": "APAGADO"}))
        self.assertTrue(latch.armed)
        self.assertTrue(latch.observe({"LED_001": "ACESO"}))

    def test_trigger_is_not_consumed_while_result_or_gpio_blocks_it(self):
        latch = F2AutomaticTriggerLatch()
        self.assertFalse(
            latch.observe({"LED_001": "ACESO"}, can_trigger=False)
        )
        self.assertTrue(latch.armed)
        self.assertTrue(
            latch.observe({"LED_001": "ACESO"}, can_trigger=True)
        )

    def test_setting_is_opt_in_and_persistent(self):
        with TemporaryDirectory() as directory:
            repository = ConfigRepository(Path(directory) / "odin_config.json")
            self.assertFalse(carregar_analise_automatica_f2(repository))
            self.assertTrue(salvar_analise_automatica_f2(repository, True))
            self.assertTrue(carregar_analise_automatica_f2(repository))
            data = repository.carregar_configuracao_existente_sem_alerta()
            self.assertTrue(data["settings"][F2_AUTO_SETTING_KEY])

    def test_overlay_is_light_and_does_not_mutate_camera_frame(self):
        frame = np.zeros((80, 180, 3), dtype=np.uint8)
        leds = [
            LedSelection(id="L1", centro_x=30, centro_y=40, raio=12),
            LedSelection(id="L2", centro_x=90, centro_y=40, raio=12),
            LedSelection(id="L3", centro_x=150, centro_y=40, raio=12),
        ]
        original = frame.copy()
        rendered = renderizar_overlay_rois_f2(
            frame,
            leds,
            {"L1": "ACESO", "L2": "APAGADO", "L3": "POUCA_LUZ"},
        )

        self.assertTrue(np.array_equal(frame, original))
        self.assertFalse(np.shares_memory(frame, rendered))
        self.assertGreater(rendered[40, 30, 1], rendered[40, 30, 2])
        self.assertGreater(rendered[40, 90, 2], rendered[40, 90, 1])
        self.assertGreater(rendered[40, 150, 1], rendered[40, 150, 0])
        self.assertGreater(rendered[40, 150, 2], rendered[40, 150, 0])
        self.assertLessEqual(F2_LIVE_ROI_OVERLAY_ALPHA, 0.15)

    def test_monitoring_cadence_is_fast_but_not_every_camera_frame(self):
        self.assertGreaterEqual(F2_AUTO_ANALYSIS_INTERVAL_S, 0.05)
        self.assertLessEqual(F2_AUTO_ANALYSIS_INTERVAL_S, 0.12)

    def test_f3_window_does_not_receive_f2_live_overlay_api(self):
        self.assertFalse(hasattr(DisplayProductionF3Window, "set_live_roi_states"))

    def test_settings_label_is_explicitly_f2_only(self):
        import inspect
        import src.platform.f2_automatic_analysis as module

        source = inspect.getsource(module)
        self.assertIn("Ativar análise automática", source)
        self.assertIn("A mesma configuração não altera o F3", source)
        self.assertIn("ao menos um LED ACESO", source)


if __name__ == "__main__":
    unittest.main()
