from __future__ import annotations

import inspect
import unittest

import numpy as np

from src.platform.display_f3_live_runtime_fix import (
    F3_TRANSIENT_HOLD_FRAMES,
    atualizar_classificacao_overlay_f3,
    estabilizar_estado_fisico_rapido_f3,
)
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp


class _PhysicalApp:
    pass


class _AnalyzerFake:
    def __init__(self, repository, result):
        self.repository = repository
        self.result = dict(result)
        self.calls = 0

    def analyze(self, **_kwargs):
        self.calls += 1
        return dict(self.result)


class _OverlayApp:
    def __init__(self, analyzer, repository):
        self.display_f3_ativo = True
        self.camera_frame_atual = np.zeros((40, 60, 3), dtype=np.uint8)
        self.display_project_repository = repository
        self._display_auto_analyzer = analyzer
        self._display_auto_last_analysis = None
        self._display_auto_last_decision = True
        self._display_auto_stable_frames = 7
        self._frame_id = 11

    @staticmethod
    def _display_auto_configuration_open():
        return False

    @staticmethod
    def _display_auto_current_context():
        return {
            "project_name": "DISPLAY_TESTE",
            "check_id": "CHECK_H1",
            "check_name": "H1",
            "current_index": 0,
        }

    def _display_auto_frame_token(self, _frame):
        return ("camera", self._frame_id)

    @staticmethod
    def _obter_rotacao_visual_display_f3():
        return 0

    def registrar_resultado_check_display_f3(self, _approved):
        raise AssertionError("classificação de overlay não pode registrar CHECK")


class DisplayF3LiveRuntimeFixTests(unittest.TestCase):
    @staticmethod
    def _check_state(check_id: str, name: str) -> dict:
        return {
            "kind": "check",
            "text": f"DISPLAY EM {name}",
            "check_id": check_id,
            "check_name": name,
            "physical_state_key": f"check:{check_id}",
            "allow_auto": False,
            "board_references_complete": True,
        }

    def test_h1_entra_imediatamente_sem_debounce_fisico_de_tres_frames(self):
        app = _PhysicalApp()
        state = estabilizar_estado_fisico_rapido_f3(
            app,
            self._check_state("CHECK_H1", "H1"),
        )

        self.assertEqual("check", state["kind"])
        self.assertEqual("CHECK_H1", state["check_id"])
        self.assertEqual("check:CHECK_H1", app._display_f3_physical_stable_key)
        self.assertEqual(0, app._display_f3_physical_pending_frames)

    def test_blue_mantem_estado_durante_fase_escura_do_pisca(self):
        app = _PhysicalApp()
        blue = self._check_state("CHECK_BLUE", "BLUE")
        estabilizar_estado_fisico_rapido_f3(app, blue)

        off = {
            "kind": "off",
            "text": "PLACA NO SUPORTE • DESLIGADA",
            "physical_state_key": "off",
            "allow_auto": False,
            "board_references_complete": True,
        }
        held = estabilizar_estado_fisico_rapido_f3(app, off)

        self.assertEqual("check", held["kind"])
        self.assertEqual("CHECK_BLUE", held["check_id"])
        self.assertTrue(held["transient_hold"])
        self.assertEqual("off", held["raw_kind_during_hold"])
        self.assertEqual(
            F3_TRANSIENT_HOLD_FRAMES - 1,
            app._display_f3_transient_hold_frames,
        )

    def test_outro_check_substitui_blue_imediatamente(self):
        app = _PhysicalApp()
        estabilizar_estado_fisico_rapido_f3(
            app,
            self._check_state("CHECK_BLUE", "BLUE"),
        )
        usb = estabilizar_estado_fisico_rapido_f3(
            app,
            self._check_state("CHECK_USB", "USB"),
        )

        self.assertEqual("CHECK_USB", usb["check_id"])
        self.assertEqual(0, app._display_f3_transient_hold_frames)
        self.assertIsNone(app._display_f3_transient_hold_state)

    def test_suporte_vazio_cancela_hold_do_blue(self):
        app = _PhysicalApp()
        estabilizar_estado_fisico_rapido_f3(
            app,
            self._check_state("CHECK_BLUE", "BLUE"),
        )
        empty = estabilizar_estado_fisico_rapido_f3(
            app,
            {
                "kind": "empty",
                "text": "PLACA FORA DO SUPORTE",
                "physical_state_key": "empty",
                "allow_auto": False,
                "board_references_complete": True,
            },
        )

        self.assertNotEqual("CHECK_BLUE", str(empty.get("check_id") or ""))
        self.assertEqual(0, app._display_f3_transient_hold_frames)
        self.assertIsNone(app._display_f3_transient_hold_state)

    def test_classificacao_overlay_roda_sem_registrar_ou_alterar_debounce(self):
        repository = object()
        analyzer = _AnalyzerFake(
            repository,
            {
                "ready": True,
                "approved": True,
                "project_name": "DISPLAY_TESTE",
                "check_id": "CHECK_H1",
                "mask_results": [
                    {"mask_id": "M1", "classified": "on", "matched": True}
                ],
            },
        )
        app = _OverlayApp(analyzer, repository)

        analysis = atualizar_classificacao_overlay_f3(app)

        self.assertEqual(1, analyzer.calls)
        self.assertIs(analysis, app._display_auto_last_analysis)
        self.assertEqual("on", analysis["mask_results"][0]["classified"])
        self.assertTrue(app._display_auto_last_decision)
        self.assertEqual(7, app._display_auto_stable_frames)

    def test_classificacao_overlay_nao_duplica_analise_valida_do_check_atual(self):
        repository = object()
        analyzer = _AnalyzerFake(repository, {})
        app = _OverlayApp(analyzer, repository)
        existing = {
            "ready": True,
            "project_name": "DISPLAY_TESTE",
            "check_id": "CHECK_H1",
            "mask_results": [{"mask_id": "M1", "classified": "off"}],
        }
        app._display_auto_last_analysis = existing

        analysis = atualizar_classificacao_overlay_f3(app)

        self.assertIs(existing, analysis)
        self.assertEqual(0, analyzer.calls)

    def test_cache_restaura_cores_se_gate_limpar_analise_no_mesmo_frame(self):
        repository = object()
        analyzer = _AnalyzerFake(
            repository,
            {
                "ready": True,
                "project_name": "DISPLAY_TESTE",
                "check_id": "CHECK_H1",
                "mask_results": [{"mask_id": "M1", "classified": "off"}],
            },
        )
        app = _OverlayApp(analyzer, repository)
        first = atualizar_classificacao_overlay_f3(app)
        app._display_auto_last_analysis = None
        second = atualizar_classificacao_overlay_f3(app)

        self.assertEqual(1, analyzer.calls)
        self.assertIs(first, second)
        self.assertIs(second, app._display_auto_last_analysis)

    def test_perfil_instala_runtime_rapido_depois_da_correcao_fisica(self):
        source = inspect.getsource(RaspberryPi3ProductionApp.__init__)
        physical_position = source.index("instalar_correcao_estado_fisico_display_f3()")
        live_position = source.index("instalar_runtime_ao_vivo_display_f3()")
        self.assertLess(physical_position, live_position)


if __name__ == "__main__":
    unittest.main()
