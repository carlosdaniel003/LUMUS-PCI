from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_unknown_debug_fix as fix_module
from src.platform.display_f3_fast_expected_gate import (
    instalar_gate_rapido_check_esperado_display_f3,
)
from src.platform.display_f3_unknown_debug_fix import (
    F3_UNKNOWN_OFF_SOURCE,
    montar_debug_tecnico_display_f3,
    resolver_unknown_com_evidencia_off_f3,
)


class _FakeRepository:
    config_file = "data/config/odin_display_projects.json"

    @staticmethod
    def obter_projeto_ativo():
        return "TESTE"


class _FakeFrame:
    shape = (1080, 1920, 3)


class _FakeApp:
    def __init__(self):
        self.display_project_repository = _FakeRepository()
        self.camera_frame_atual = _FakeFrame()
        self.camera_ultimo_frame_id = 321
        self._display_f3_operational_matcher = None
        self._display_f3_operational_state = {
            "kind": "unknown",
            "text": "IDENTIFICANDO...",
            "allow_auto": False,
            "unknown_off_diagnostics": {
                "blocked_reason": "score_off_muito_baixo",
                "off_score": 0.51,
                "off_threshold": 0.72,
                "empty_score": 0.33,
            },
        }
        self._display_auto_last_analysis = None
        self._display_auto_last_decision = None
        self._display_auto_stable_frames = 0
        self._display_auto_transition_frames = 0
        self._display_f3_physical_stable_key = ""
        self._display_f3_physical_pending_key = ""
        self._display_f3_physical_pending_frames = 0
        self._display_f3_unknown_off_pending_frames = 0
        self._display_auto_manual_entry_signature = None
        self._display_auto_manual_entry_label = ""
        self._display_f3_waiting_empty_rearm = False

    @staticmethod
    def _display_auto_current_context():
        return {
            "project_name": "TESTE",
            "current_index": 0,
            "check_id": "CHECK_H1",
            "check_name": "H1",
        }

    @staticmethod
    def _obter_rotacao_visual_display_f3():
        return 180


class DisplayF3UnknownDebugFixTests(unittest.TestCase):
    def test_unknown_vira_off_quando_presenca_e_mascaras_concordam(self):
        state = resolver_unknown_com_evidencia_off_f3(
            {
                "kind": "unknown",
                "text": "IDENTIFICANDO...",
                "board_references_complete": True,
                "configured_count": 6,
            },
            evidence={
                "available": True,
                "off_confirmed": True,
                "off_votes": 8,
                "powered_votes": 0,
                "valid_votes": 8,
            },
            off_score=0.66,
            off_threshold=0.72,
            empty_score=0.39,
            board_references_complete=True,
        )

        self.assertEqual("off", state["kind"])
        self.assertFalse(state["allow_auto"])
        self.assertEqual(F3_UNKNOWN_OFF_SOURCE, state["source"])
        self.assertTrue(state["unknown_off_diagnostics"]["resolved"])

    def test_unknown_nao_vira_off_quando_score_global_e_muito_baixo(self):
        state = resolver_unknown_com_evidencia_off_f3(
            {"kind": "unknown"},
            evidence={"available": True, "off_confirmed": True},
            off_score=0.41,
            off_threshold=0.72,
            empty_score=0.20,
            board_references_complete=True,
        )

        self.assertEqual("unknown", state["kind"])
        self.assertEqual(
            "score_off_muito_baixo",
            state["unknown_off_diagnostics"]["blocked_reason"],
        )

    def test_unknown_nao_vira_off_se_suporte_vazio_parece_mais_provavel(self):
        state = resolver_unknown_com_evidencia_off_f3(
            {"kind": "unknown"},
            evidence={"available": True, "off_confirmed": True},
            off_score=0.65,
            off_threshold=0.72,
            empty_score=0.64,
            board_references_complete=True,
        )

        self.assertEqual("unknown", state["kind"])
        self.assertEqual(
            "off_nao_supera_suporte_vazio",
            state["unknown_off_diagnostics"]["blocked_reason"],
        )

    def test_unknown_nao_vira_off_sem_votacao_das_mascaras(self):
        state = resolver_unknown_com_evidencia_off_f3(
            {"kind": "unknown"},
            evidence={
                "available": True,
                "off_confirmed": False,
                "off_votes": 3,
                "powered_votes": 3,
                "valid_votes": 6,
            },
            off_score=0.68,
            off_threshold=0.72,
            empty_score=0.30,
            board_references_complete=True,
        )

        self.assertEqual("unknown", state["kind"])
        self.assertEqual(
            "mascaras_nao_confirmam_off",
            state["unknown_off_diagnostics"]["blocked_reason"],
        )

    def test_debug_tecnico_e_autocontido_para_copiar_e_colar(self):
        text = montar_debug_tecnico_display_f3(_FakeApp())

        self.assertIn("ODIN DISPLAY F3 - DEBUG TÉCNICO", text)
        self.assertIn("projeto=TESTE", text)
        self.assertIn("frame_shape=1080x1920x3", text)
        self.assertIn("visual_rotation=180", text)
        self.assertIn("[CHECK LÓGICO]", text)
        self.assertIn("check_name=H1", text)
        self.assertIn("[ESTADO FÍSICO FINAL]", text)
        self.assertIn("kind=unknown", text)
        self.assertIn("[FALLBACK UNKNOWN -> OFF]", text)
        self.assertIn("blocked_reason=score_off_muito_baixo", text)
        self.assertIn("[RUNTIME / DEBOUNCE]", text)
        self.assertIn("Cole este bloco inteiro", text)

    def test_correcao_final_e_instalada_depois_do_fast_gate(self):
        source = inspect.getsource(instalar_gate_rapido_check_esperado_display_f3)
        fast_position = source.index(
            "DisplayAutomaticCheckF3Mixin._display_f3_fast_expected_gate_installed"
        )
        fix_position = source.index(
            "instalar_correcao_unknown_e_debug_display_f3()"
        )
        self.assertLess(fast_position, fix_position)

    def test_modulo_novo_nao_depende_do_runtime_f2(self):
        source = inspect.getsource(fix_module)
        for forbidden in (
            "src.platform.f2_",
            "F2Automatic",
            "operacao_engine",
            "linux_f2_fixed_resolution",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
