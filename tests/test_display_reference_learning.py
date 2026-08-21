from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.platform.display_project_repository import DisplayProjectRepository
from src.platform.display_reference_learning import (
    DisplayReferenceMaskEditorWindow,
    display_mask_to_led_selection,
    learn_display_reference,
)
from src.platform.display_reference_store import (
    MAX_DISPLAY_REFERENCES_PER_STATE,
    DisplayReferenceLearningStore,
    DisplayReferenceLimitError,
    display_learning_path_for_repository,
)


def _sample(value: float, ident: str) -> dict:
    return {
        "id": ident,
        "image_path": f"{ident}.png",
        "features": {
            "v_mean": float(value),
            "h_mean": 20.0,
            "area_pixels": 10,
        },
        "mask": {
            "id": "MASK_001",
            "type": "circle",
            "cx": 30,
            "cy": 30,
            "radius": 8,
        },
    }


class DisplayReferenceLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_file = self.root / "display_projects.json"
        self.repo = DisplayProjectRepository(self.project_file)
        self.assertTrue(self.repo.adicionar_projeto("DISPLAY A", (120, 80)))
        self.assertTrue(self.repo.adicionar_projeto("DISPLAY B", (120, 80)))
        self.learning_file = display_learning_path_for_repository(self.repo)
        self.store = DisplayReferenceLearningStore(self.learning_file)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_arquivo_de_aprendizado_e_separado_do_projeto_e_do_f2(self):
        self.assertNotEqual(self.project_file, self.learning_file)
        self.assertNotIn("odin_pci_config", str(self.learning_file))

        fake_f2 = self.root / "odin_pci_config.json"
        fake_f2.write_bytes(b'{"f2":"intacto"}')
        before = fake_f2.read_bytes()
        self.store.save_sample("DISPLAY A", "on", _sample(100, "a"), scope="project")
        self.assertEqual(before, fake_f2.read_bytes())

    def test_global_serve_para_todos_os_projetos_display(self):
        self.store.save_sample("DISPLAY A", "on", _sample(100, "global"), scope="global")
        refs_a = self.store.active_references("DISPLAY A", "on")
        refs_b = self.store.active_references("DISPLAY B", "on")
        self.assertEqual(1, len(refs_a))
        self.assertEqual(1, len(refs_b))
        self.assertEqual("global", refs_a[0]["scope"])
        self.assertEqual("global", refs_b[0]["scope"])

    def test_referencia_de_projeto_nao_vaza_para_outro_projeto(self):
        self.store.save_sample("DISPLAY A", "off", _sample(40, "local"), scope="project")
        self.assertEqual(1, len(self.store.active_references("DISPLAY A", "off")))
        self.assertEqual(0, len(self.store.active_references("DISPLAY B", "off")))

    def test_limite_de_tres_e_soma_global_mais_projeto(self):
        self.store.save_sample("DISPLAY A", "on", _sample(10, "g1"), scope="global")
        self.store.save_sample("DISPLAY A", "on", _sample(20, "p1"), scope="project")
        self.store.save_sample("DISPLAY A", "on", _sample(30, "p2"), scope="project")
        self.assertEqual(
            MAX_DISPLAY_REFERENCES_PER_STATE,
            len(self.store.active_references("DISPLAY A", "on")),
        )
        with self.assertRaises(DisplayReferenceLimitError):
            self.store.save_sample("DISPLAY A", "on", _sample(40, "p3"), scope="project")

    def test_nova_global_nao_pode_estourar_projeto_existente(self):
        self.store.save_sample("DISPLAY A", "low_light", _sample(10, "p1"), scope="project")
        self.store.save_sample("DISPLAY A", "low_light", _sample(20, "p2"), scope="project")
        self.store.save_sample("DISPLAY A", "low_light", _sample(30, "g1"), scope="global")
        with self.assertRaises(DisplayReferenceLimitError):
            self.store.save_sample("DISPLAY A", "low_light", _sample(40, "g2"), scope="global")

    def test_aprendizado_agrega_as_amostras_ativas(self):
        self.store.save_sample("DISPLAY A", "on", _sample(100, "a"), scope="project")
        self.store.save_sample("DISPLAY A", "on", _sample(200, "b"), scope="project")
        learned = self.store.learned_features("DISPLAY A", "on")
        self.assertIsNotNone(learned)
        self.assertAlmostEqual(150.0, learned.v_mean)
        snapshot = self.store.learning_snapshot("DISPLAY A")
        self.assertEqual(2, snapshot["on"]["count"])
        self.assertIsNotNone(snapshot["on"]["features"])

    def test_mover_escopo_preserva_amostra_e_aprendizado(self):
        self.store.save_sample("DISPLAY A", "off", _sample(50, "x"), scope="project")
        before = self.store.learned_features("DISPLAY A", "off").v_mean
        self.store.move_scope("DISPLAY A", "off", "project", 0)
        refs = self.store.active_references("DISPLAY B", "off")
        self.assertEqual(1, len(refs))
        self.assertEqual("global", refs[0]["scope"])
        self.assertEqual(before, self.store.learned_features("DISPLAY A", "off").v_mean)

    def test_renomear_e_remover_projeto_sincroniza_biblioteca(self):
        self.store.save_sample("DISPLAY A", "on", _sample(80, "local"), scope="project")
        # Hooks são instalados ao importar display_reference_learning.
        self.assertTrue(self.repo.renomear_projeto("DISPLAY A", "DISPLAY NOVO"))
        self.assertEqual(1, len(self.store.active_references("DISPLAY NOVO", "on")))
        self.assertEqual(0, len(self.store.active_references("DISPLAY A", "on")))
        self.assertTrue(self.repo.remover_projeto("DISPLAY NOVO"))
        self.assertEqual(0, len(self.store.active_references("DISPLAY NOVO", "on")))

    def test_conversao_de_circulo_segmento_e_poligono_para_extrator(self):
        circle = display_mask_to_led_selection({
            "id": "C",
            "type": "circle",
            "cx": 40,
            "cy": 35,
            "radius": 10,
        })
        segment = display_mask_to_led_selection({
            "id": "S",
            "type": "segment",
            "cx": 50,
            "cy": 40,
            "width": 30,
            "height": 8,
            "angle": 25,
        })
        polygon = display_mask_to_led_selection({
            "id": "P",
            "type": "polygon",
            "points": [[20, 20], [45, 20], [50, 35], [25, 42]],
        })
        self.assertTrue(circle.eh_circulo)
        self.assertTrue(segment.eh_segmento)
        self.assertTrue(polygon.eh_segmento_livre)

    def test_aprendizado_real_usa_features_da_mascara(self):
        frame = np.zeros((80, 120, 3), dtype=np.uint8)
        frame[20:50, 30:70] = (40, 180, 240)
        learned = learn_display_reference(
            frame,
            {
                "id": "MASK_001",
                "type": "segment",
                "cx": 50,
                "cy": 35,
                "width": 32,
                "height": 10,
                "angle": 0,
            },
        )
        self.assertIn("v_mean", learned["features"])
        self.assertGreater(learned["features"]["area_pixels"], 0)
        self.assertEqual("MASK_001", learned["mask"]["id"])

    def test_editor_de_referencia_e_o_mesmo_editor_display_com_restricao_de_uma_roi(self):
        self.assertTrue(issubclass(DisplayReferenceMaskEditorWindow, __import__(
            "src.platform.display_mask_editor",
            fromlist=["DisplayMaskEditorWindow"],
        ).DisplayMaskEditorWindow))
        source = inspect.getsource(DisplayReferenceMaskEditorWindow.save)
        self.assertIn("len(masks) != 1", source)
        self.assertIn("exatamente uma máscara", source)

    def test_modulos_de_referencia_f3_nao_usam_config_repository_ou_projeto_led(self):
        modules = (
            __import__("src.platform.display_reference_store", fromlist=["x"]),
            __import__("src.platform.display_reference_learning", fromlist=["x"]),
        )
        source = "\n".join(inspect.getsource(module) for module in modules)
        for forbidden in (
            "ConfigRepository",
            "led_projects",
            "projeto_led_ativo",
            "operacao_engine",
            "operacao_total",
            "operacao_ok",
            "operacao_ng",
        ):
            self.assertNotIn(forbidden, source)

    def test_round_trip_reabre_referencias_e_aprendizado(self):
        self.store.save_sample("DISPLAY A", "on", _sample(77, "round"), scope="project")
        reopened = DisplayReferenceLearningStore(self.learning_file)
        refs = reopened.active_references("DISPLAY A", "on")
        self.assertEqual(1, len(refs))
        self.assertEqual("round", refs[0]["sample"]["id"])
        self.assertAlmostEqual(77.0, reopened.learned_features("DISPLAY A", "on").v_mean)


if __name__ == "__main__":
    unittest.main()
