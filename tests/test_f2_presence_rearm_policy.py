from __future__ import annotations

from types import SimpleNamespace
import unittest

import numpy as np

from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED,
    F2AutomaticCycleGuardMixin,
    F2AutomaticCycleState,
    F2VisualBoardRemovalDetector,
)
from src.platform.f2_automatic_presence_cycle_policy import (
    F2AutomaticPresenceCyclePolicyMixin,
)
from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_PRESENT,
    F2_BOARD_PRESENCE_UNKNOWN,
)


class _Engine:
    ready = True

    def __init__(self) -> None:
        self.status = "APAGADO"

    def analyze(self, _frame):
        return SimpleNamespace(
            results=[SimpleNamespace(id="LED_001", status=self.status)]
        )


class _AutomaticHarness(F2AutomaticPresenceCyclePolicyMixin):
    def __init__(self) -> None:
        self.operacao_engine = _Engine()
        self.camera_frame_atual = np.zeros((20, 20, 3), dtype=np.uint8)
        self.operacao_processando = False
        self.operacao_total = 0
        self._operacao_resultado_after_id = None
        self._presence = F2_BOARD_PRESENCE_PRESENT
        self._f2_auto_cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        self._f2_auto_reference_empty_frames = 0
        self._f2_auto_last_raw_states = {}
        self._f2_auto_last_states = {}
        self._f2_auto_last_presence = None

    def _f2_auto_enabled(self) -> bool:
        return True

    def _f2_auto_fresh_analysis_due(self) -> bool:
        return True

    def _f2_auto_presence(self, _frame):
        return self._presence, {}

    def _f2_auto_result_hold_active(self) -> bool:
        return False

    def _f2_auto_observe_removal(self, frame, presence: str) -> bool:
        return F2AutomaticCycleGuardMixin._f2_auto_observe_removal(
            self,
            frame,
            presence,
        )

    def _f2_auto_publish_states(self, states, _presence) -> None:
        self._f2_auto_last_states = dict(states)

    def _f2_auto_can_trigger(self) -> bool:
        return True

    def disparar_inspecao_operacao(self) -> None:
        self.operacao_total += 1
        self._f2_auto_cycle.mark_inspected()
        self._f2_auto_reference_empty_frames = 0


class _ManualBase:
    def _f2_auto_enabled(self) -> bool:
        return True

    def disparar_inspecao_operacao(self) -> None:
        self.operacao_total += 1


class _ManualHarness(F2AutomaticCycleGuardMixin, _ManualBase):
    pass


class F2PresenceRearmPolicyTests(unittest.TestCase):
    def test_led_aceso_dispara_sem_usar_presenca_como_gate(self):
        app = _AutomaticHarness()
        app._presence = F2_BOARD_PRESENCE_UNKNOWN
        app.operacao_engine.status = "ACESO"

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)

    def test_fluxo_completo_exige_ausencia_antes_da_proxima_automatica(self):
        app = _AutomaticHarness()

        # Placa 1 colocada e ligada: dois frames estáveis com LED ACESO.
        app._presence = F2_BOARD_PRESENCE_PRESENT
        app.operacao_engine.status = "ACESO"
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)

        # A mesma placa é desligada. Isso NÃO libera novo ciclo.
        app.operacao_engine.status = "APAGADO"
        for _ in range(20):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertEqual(1, app.operacao_total)

        # Se a mesma placa for ligada novamente, continua bloqueada.
        app.operacao_engine.status = "ACESO"
        for _ in range(20):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertEqual(1, app.operacao_total)

        # Mesmo uma cena ambígua não conta como retirada.
        app._presence = F2_BOARD_PRESENCE_UNKNOWN
        app.operacao_engine.status = "APAGADO"
        for _ in range(8):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)

        # Somente SUPORTE VAZIO confirmado rearma o automático.
        app._presence = F2_BOARD_PRESENCE_EMPTY
        for _ in range(F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertFalse(app._f2_auto_cycle.waiting_removal)

        # Placa 2 entra desligada: ainda não há análise.
        app._presence = F2_BOARD_PRESENCE_PRESENT
        for _ in range(5):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)

        # Placa 2 liga: agora um novo ciclo automático é permitido.
        app.operacao_engine.status = "ACESO"
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(2, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)

    def test_enter_manual_continua_analisando_mesmo_com_ciclo_travado(self):
        app = object.__new__(_ManualHarness)
        app.operacao_total = 0
        app._f2_auto_cycle = F2AutomaticCycleState()
        app._f2_auto_cycle.mark_inspected()
        app._f2_auto_reference_empty_frames = 0
        app._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        app._f2_board_presence_refs = None
        app.camera_frame_atual = None
        app.operacao_leds_preview = ()

        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        app.disparar_inspecao_operacao()
        app.disparar_inspecao_operacao()

        self.assertEqual(2, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)


if __name__ == "__main__":
    unittest.main()
