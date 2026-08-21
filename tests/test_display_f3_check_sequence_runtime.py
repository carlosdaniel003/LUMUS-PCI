from __future__ import annotations

import inspect
import unittest

from src.platform.display_check_sequence_runtime import DisplayCheckSequenceRuntime
from src.platform.display_production_f3 import DisplayProductionF3Mixin
from src.platform.display_production_f3_window import DisplayProductionF3Window


CHECKS = [
    {"id": "CHECK_001", "name": "H1"},
    {"id": "CHECK_002", "name": "BLUE"},
    {"id": "CHECK_003", "name": "AUX"},
    {"id": "CHECK_004", "name": "USB"},
]


class DisplayF3CheckSequenceRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = DisplayCheckSequenceRuntime()
        self.runtime.configurar_checks(CHECKS)

    def test_inicia_aguardando_primeiro_check(self):
        snapshot = self.runtime.snapshot()
        self.assertEqual("H1", snapshot["current_check"]["name"])
        self.assertEqual(0, snapshot["current_index"])
        self.assertEqual(
            ["current", "pending", "pending", "pending"],
            [item["state"] for item in snapshot["checks"]],
        )
        self.assertEqual((0, 0, 0), (snapshot["total"], snapshot["ok"], snapshot["ng"]))

    def test_avanca_h1_blue_aux_usb_e_aprova_placa(self):
        esperado = ["BLUE", "AUX", "USB"]
        for nome in esperado:
            evento = self.runtime.registrar_resultado_check(True)
            self.assertEqual(DisplayCheckSequenceRuntime.EVENT_ADVANCED, evento["event"])
            self.assertEqual(nome, evento["snapshot"]["current_check"]["name"])

        evento = self.runtime.registrar_resultado_check(True)
        self.assertEqual(DisplayCheckSequenceRuntime.EVENT_PLATE_OK, evento["event"])
        snapshot = evento["snapshot"]
        self.assertEqual((1, 1, 0), (snapshot["total"], snapshot["ok"], snapshot["ng"]))
        self.assertEqual("H1", snapshot["current_check"]["name"])
        self.assertEqual(0, snapshot["current_index"])
        self.assertEqual(4, len(evento["completed_ids"]))

    def test_descartar_no_meio_soma_ng_e_reinicia_primeiro_check(self):
        self.runtime.registrar_resultado_check(True)
        self.runtime.registrar_resultado_check(True)
        self.assertEqual("AUX", self.runtime.snapshot()["current_check"]["name"])

        evento = self.runtime.descartar_placa()

        self.assertEqual(DisplayCheckSequenceRuntime.EVENT_PLATE_DISCARDED, evento["event"])
        snapshot = evento["snapshot"]
        self.assertEqual((1, 0, 1), (snapshot["total"], snapshot["ok"], snapshot["ng"]))
        self.assertEqual("H1", snapshot["current_check"]["name"])
        self.assertEqual((), snapshot["completed_ids"])

    def test_check_reprovado_contabiliza_ng_e_reinicia(self):
        self.runtime.registrar_resultado_check(True)
        evento = self.runtime.registrar_resultado_check(False)
        self.assertEqual(DisplayCheckSequenceRuntime.EVENT_PLATE_NG, evento["event"])
        self.assertEqual("BLUE", evento["failed_check"]["name"])
        snapshot = evento["snapshot"]
        self.assertEqual((1, 0, 1), (snapshot["total"], snapshot["ok"], snapshot["ng"]))
        self.assertEqual("H1", snapshot["current_check"]["name"])

    def test_contadores_de_sessao_sao_preservados_ao_reconfigurar_checks(self):
        for _ in range(4):
            self.runtime.registrar_resultado_check(True)
        self.runtime.configurar_checks(
            [
                {"id": "CHECK_001", "name": "START"},
                {"id": "CHECK_002", "name": "FINAL"},
            ]
        )
        snapshot = self.runtime.snapshot()
        self.assertEqual((1, 1, 0), (snapshot["total"], snapshot["ok"], snapshot["ng"]))
        self.assertEqual("START", snapshot["current_check"]["name"])

    def test_runtime_puro_nao_importa_f2_camera_ou_tkinter(self):
        modulo = __import__(
            "src.platform.display_check_sequence_runtime",
            fromlist=["DisplayCheckSequenceRuntime"],
        )
        fonte = inspect.getsource(modulo)
        self.assertNotIn("tkinter", fonte)
        self.assertNotIn("camera_service", fonte)
        self.assertNotIn("OperationEngine", fonte)
        self.assertNotIn("SegmentDisplayRuntimeMixin", fonte)
        self.assertNotIn("operacao_window", fonte)

    def test_f3_expoe_api_de_avanco_sem_sobrescrever_trigger_f2(self):
        self.assertIn("registrar_resultado_check_display_f3", DisplayProductionF3Mixin.__dict__)
        self.assertIn("concluir_check_display_f3", DisplayProductionF3Mixin.__dict__)
        self.assertIn("descartar_placa_display_f3", DisplayProductionF3Mixin.__dict__)
        self.assertNotIn("disparar_inspecao_operacao", DisplayProductionF3Mixin.__dict__)
        self.assertNotIn("_evento_enter_pressionado", DisplayProductionF3Mixin.__dict__)

    def test_janela_f3_tem_tecla_1_e_botao_de_descarte(self):
        fonte = inspect.getsource(DisplayProductionF3Window.__init__)
        self.assertIn('self.container.bind("<KeyPress-1>", self._handle_discard)', fonte)
        self.assertIn('self.container.bind("<KP_1>", self._handle_discard)', fonte)
        self.assertIn('text="DESCARTAR PLACA  [1]"', fonte)

    def test_janela_f3_exibe_cards_e_contadores_separados(self):
        fonte = inspect.getsource(DisplayProductionF3Window)
        self.assertIn("check_flow_frame", fonte)
        self.assertIn("CONCLUÍDO", fonte)
        self.assertIn("AGUARDANDO", fonte)
        self.assertIn("PRÓXIMO", fonte)
        self.assertIn("self._set_counters", fonte)
        self.assertNotIn("operacao_total", fonte)
        self.assertNotIn("operacao_ok", fonte)
        self.assertNotIn("operacao_ng", fonte)


if __name__ == "__main__":
    unittest.main()
