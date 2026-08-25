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
    F2_AUTO_NEW_BOARD_OFF_FRAMES_REQUIRED,
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


class _AutomaticBase:
    def disparar_inspecao_operacao(self) -> None:
        self.lock_seen_during_dispatch = bool(
            getattr(self, "_f2_auto_cycle_locked", False)
        )
        if self.increment_operation_total:
            self.operacao_total += 1


class _AutomaticHarness(
    F2AutomaticPresenceCyclePolicyMixin,
    F2AutomaticCycleGuardMixin,
    _AutomaticBase,
):
    def __init__(self) -> None:
        self.operacao_engine = _Engine()
        self.camera_frame_atual = np.zeros((20, 20, 3), dtype=np.uint8)
        self.operacao_leds_preview = ()
        self.operacao_processando = False
        self.operacao_total = 0
        self.increment_operation_total = True
        self.lock_seen_during_dispatch = False
        self._operacao_resultado_after_id = None
        self._presence = F2_BOARD_PRESENCE_PRESENT
        self._f2_auto_cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        self._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        self._f2_auto_reference_empty_frames = 0
        self._f2_auto_last_raw_states = {}
        self._f2_auto_last_states = {}
        self._f2_auto_last_presence = None
        self._f2_auto_cycle_locked = False
        self._f2_auto_waiting_new_board_off = False
        self._f2_auto_new_board_off_frames = 0
        self._f2_board_presence_refs = None

    def _f2_auto_enabled(self) -> bool:
        return True

    def _f2_auto_fresh_analysis_due(self) -> bool:
        return True

    def _f2_auto_presence(self, _frame):
        return self._presence, {}

    def _f2_auto_result_hold_active(self) -> bool:
        return False

    def _f2_auto_publish_states(self, states, _presence) -> None:
        self._f2_auto_last_states = dict(states)

    def _f2_auto_can_trigger(self) -> bool:
        return True


class _ManualBase:
    def _f2_auto_enabled(self) -> bool:
        return True

    def disparar_inspecao_operacao(self) -> None:
        self.operacao_total += 1


class _ManualHarness(
    F2AutomaticPresenceCyclePolicyMixin,
    F2AutomaticCycleGuardMixin,
    _ManualBase,
):
    pass


class F2PresenceRearmPolicyTests(unittest.TestCase):
    def test_led_aceso_dispara_sem_usar_presenca_como_gate_inicial(self):
        app = _AutomaticHarness()
        app._presence = F2_BOARD_PRESENCE_UNKNOWN
        app.operacao_engine.status = "ACESO"

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)

    def test_disparo_consume_trava_antes_de_entrar_na_inspecao_oficial(self):
        app = _AutomaticHarness()
        app.operacao_engine.status = "ACESO"

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())

        self.assertTrue(app.lock_seen_during_dispatch)
        self.assertTrue(app._f2_auto_cycle_locked)
        self.assertEqual(1, app.operacao_total)

    def test_disparo_real_marca_placa_como_ja_analisada(self):
        app = _AutomaticHarness()
        app.operacao_engine.status = "ACESO"

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)

        # O resultado pode sumir e os LEDs podem continuar acesos por tempo
        # indefinido: a mesma placa não dispara novamente.
        for _ in range(100):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle_locked)

    def test_trava_independente_resiste_perda_do_waiting_removal(self):
        app = _AutomaticHarness()
        app.operacao_engine.status = "ACESO"

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle_locked)

        # Simula exatamente uma interferência de outra camada depois do hold
        # do resultado: mesmo que o estado secundário waiting_removal seja
        # perdido, a trava física independente continua autoritativa.
        app._f2_auto_cycle.waiting_removal = False
        app._operacao_resultado_after_id = None
        for _ in range(100):
            self.assertFalse(app._f2_auto_analyze_current_frame())

        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle_locked)

    def test_disparo_que_nao_inicia_inspecao_desfaz_trava_para_tentar_de_novo(self):
        app = _AutomaticHarness()
        app.operacao_engine.status = "ACESO"
        app.increment_operation_total = False

        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertEqual(0, app.operacao_total)
        self.assertFalse(app._f2_auto_cycle_locked)
        self.assertFalse(app._f2_auto_cycle.waiting_removal)

        app.increment_operation_total = True
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle_locked)

    def test_fluxo_completo_exige_vazio_e_nova_placa_apagada(self):
        app = _AutomaticHarness()

        # Placa 1 colocada e ligada: dois frames estáveis com LED ACESO.
        app._presence = F2_BOARD_PRESENCE_PRESENT
        app.operacao_engine.status = "ACESO"
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)

        # A mesma placa é desligada. Isso NÃO libera novo ciclo.
        app.operacao_engine.status = "APAGADO"
        for _ in range(20):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)
        self.assertEqual(1, app.operacao_total)

        # Se a mesma placa for ligada novamente, continua bloqueada.
        app.operacao_engine.status = "ACESO"
        for _ in range(20):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)
        self.assertEqual(1, app.operacao_total)

        # Mesmo uma cena ambígua não conta como retirada.
        app._presence = F2_BOARD_PRESENCE_UNKNOWN
        app.operacao_engine.status = "APAGADO"
        for _ in range(8):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)

        # SUPORTE VAZIO confirma que a placa anterior saiu, porém ainda NÃO
        # libera o próximo gatilho automático.
        app._presence = F2_BOARD_PRESENCE_EMPTY
        for _ in range(F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertFalse(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_waiting_new_board_off)
        self.assertTrue(app._f2_auto_cycle_locked)
        self.assertEqual(1, app.operacao_total)

        # Mesmo que alguma ROI do suporte vazio pareça acesa, o automático
        # continua bloqueado enquanto não entrar uma nova placa apagada.
        app.operacao_engine.status = "ACESO"
        for _ in range(10):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_waiting_new_board_off)
        self.assertTrue(app._f2_auto_cycle_locked)

        # Se a nova placa entrar já ligada, também não libera: o processo
        # físico esperado é nova placa presente e apagada antes de ligar.
        app._presence = F2_BOARD_PRESENCE_PRESENT
        for _ in range(10):
            self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertEqual(1, app.operacao_total)
        self.assertTrue(app._f2_auto_waiting_new_board_off)
        self.assertTrue(app._f2_auto_cycle_locked)

        # Nova placa presente e apagada libera o ciclo após confirmação.
        app.operacao_engine.status = "APAGADO"
        for _ in range(F2_AUTO_NEW_BOARD_OFF_FRAMES_REQUIRED - 1):
            self.assertFalse(app._f2_auto_analyze_current_frame())
            self.assertTrue(app._f2_auto_waiting_new_board_off)
            self.assertTrue(app._f2_auto_cycle_locked)
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertFalse(app._f2_auto_waiting_new_board_off)
        self.assertFalse(app._f2_auto_cycle_locked)
        self.assertEqual(1, app.operacao_total)

        # Só agora, quando a nova placa liga, nasce a segunda automática.
        app.operacao_engine.status = "ACESO"
        self.assertFalse(app._f2_auto_analyze_current_frame())
        self.assertTrue(app._f2_auto_analyze_current_frame())
        self.assertEqual(2, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)

    def test_enter_manual_continua_analisando_mesmo_com_ciclo_travado(self):
        app = object.__new__(_ManualHarness)
        app.operacao_total = 0
        app._f2_auto_cycle = F2AutomaticCycleState()
        app._f2_auto_cycle.mark_inspected()
        app._f2_auto_cycle_locked = True
        app._f2_auto_reference_empty_frames = 0
        app._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        app._f2_board_presence_refs = None
        app._f2_auto_waiting_new_board_off = False
        app._f2_auto_new_board_off_frames = 0
        app.camera_frame_atual = None
        app.operacao_leds_preview = ()

        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)
        app.disparar_inspecao_operacao()
        app.disparar_inspecao_operacao()

        self.assertEqual(2, app.operacao_total)
        self.assertTrue(app._f2_auto_cycle.waiting_removal)
        self.assertTrue(app._f2_auto_cycle_locked)


if __name__ == "__main__":
    unittest.main()
