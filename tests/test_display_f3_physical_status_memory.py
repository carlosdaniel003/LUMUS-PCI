from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import src.platform.display_f3_physical_status_memory as module


class _Repository:
    pass


class _Matcher:
    pass


class _App:
    def __init__(self):
        self.display_project_repository = _Repository()
        self._display_f3_operational_matcher = _Matcher()


class DisplayF3PhysicalStatusMemoryTests(unittest.TestCase):
    def test_qualquer_check_aprovado_pode_ser_memorizado(self):
        app = _App()
        ok = module.lembrar_check_fisico_confirmado_f3(
            app,
            {
                "project_name": "PROJETO_X",
                "check_id": "CHECK_005",
                "check_name": "SPDIF",
            },
        )
        self.assertTrue(ok)
        self.assertEqual("CHECK_005", app._display_f3_physical_status_memory_check_id)
        self.assertEqual("SPDIF", app._display_f3_physical_status_memory_check_name)

    def test_falso_off_vira_status_ligado_sem_mudar_gate(self):
        app = _App()
        module.lembrar_check_fisico_confirmado_f3(
            app,
            {
                "project_name": "PROJETO_X",
                "check_id": "CHECK_AUX",
                "check_name": "AUX",
            },
        )
        state = {
            "kind": "off",
            "text": "PLACA NO SUPORTE • DESLIGADA",
            "allow_auto": False,
            "decision_allowed": False,
            "physical_state_key": "off",
        }
        evidence = {
            "available": True,
            "valid_votes": 12,
            "powered_votes": 12,
            "off_votes": 0,
        }

        with patch.object(
            module.physical_policy_module,
            "avaliar_evidencia_energia_check_pelas_mascaras_f3",
            return_value=evidence,
        ):
            result = module.aplicar_memoria_status_fisico_f3(
                app,
                state,
                frame=object(),
                project_name="PROJETO_X",
            )

        self.assertEqual("off", result["kind"], "não pode alterar autoridade física")
        self.assertFalse(result["allow_auto"], "não pode liberar o sequenciador")
        self.assertFalse(result["decision_allowed"])
        self.assertIn("LIGADA", result["text"])
        self.assertIn("DISPLAY EM AUX", result["text"])
        self.assertTrue(result["physical_status_memory_override"])
        self.assertEqual("off", result["physical_status_memory_underlying_kind"])

    def test_off_real_continua_desligada_quando_mascaras_confirmam_off(self):
        app = _App()
        module.lembrar_check_fisico_confirmado_f3(
            app,
            {
                "project_name": "PROJETO_X",
                "check_id": "CHECK_AUX",
                "check_name": "AUX",
            },
        )
        state = {
            "kind": "off",
            "text": "PLACA NO SUPORTE • DESLIGADA",
            "allow_auto": False,
        }
        evidence = {
            "available": True,
            "valid_votes": 12,
            "powered_votes": 0,
            "off_votes": 12,
        }

        with patch.object(
            module.physical_policy_module,
            "avaliar_evidencia_energia_check_pelas_mascaras_f3",
            return_value=evidence,
        ):
            result = module.aplicar_memoria_status_fisico_f3(
                app,
                state,
                frame=object(),
                project_name="PROJETO_X",
            )

        self.assertEqual("off", result["kind"])
        self.assertIn("DESLIGADA", result["text"])
        self.assertNotIn("physical_status_memory_override", result)

    def test_empty_limpa_memoria_para_nova_placa(self):
        app = _App()
        module.lembrar_check_fisico_confirmado_f3(
            app,
            {
                "project_name": "PROJETO_X",
                "check_id": "CHECK_005",
                "check_name": "FUTURO",
            },
        )
        result = module.aplicar_memoria_status_fisico_f3(
            app,
            {"kind": "empty", "text": "PLACA FORA DO SUPORTE", "allow_auto": False},
            frame=object(),
            project_name="PROJETO_X",
        )
        self.assertEqual("empty", result["kind"])
        self.assertEqual("", app._display_f3_physical_status_memory_check_id)
        self.assertEqual("suporte_vazio", app._display_f3_physical_status_memory_reason)

    def test_regra_de_energia_exige_maioria_forte(self):
        self.assertTrue(
            module.evidencia_confirma_check_ainda_ligado_f3(
                {
                    "available": True,
                    "valid_votes": 15,
                    "powered_votes": 15,
                    "off_votes": 0,
                }
            )
        )
        self.assertFalse(
            module.evidencia_confirma_check_ainda_ligado_f3(
                {
                    "available": True,
                    "valid_votes": 15,
                    "powered_votes": 7,
                    "off_votes": 6,
                }
            )
        )

    def test_modulo_e_exclusivo_do_f3(self):
        source = inspect.getsource(module)
        for forbidden in (
            "src.platform.f2_",
            "F2Automatic",
            "linux_f2_fixed_resolution",
            "operacao_engine",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
