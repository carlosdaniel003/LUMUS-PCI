from __future__ import annotations

from threading import RLock
import inspect
import unittest

import numpy as np

from src.models.led_selection import LedSelection
from src.platform.fixed_mask_geometry_guard import copiar_mascaras_absolutas
from src.platform.led_mask_resolution_sync import (
    adapt_led_masks_to_resolution,
    canonicalize_led_mask,
)
from src.platform.project_mask_geometry_anchor import (
    ProjectMaskGeometryAnchorMixin,
)


class FakeRepository:
    def __init__(self, leds, project="PCI_640") -> None:
        self.leds = copiar_mascaras_absolutas(leds)
        self.project = project

    def obter_projeto_led_ativo(self):
        return self.project

    def carregar_leds_fixos(self, projeto=None):
        if projeto is not None and projeto != self.project:
            return []
        return copiar_mascaras_absolutas(self.leds)


class DummyBase:
    def __init__(self, leds, frame_resolution=(640, 480)) -> None:
        self._projeto_led_sessao_carregado = "PCI_640"
        self.projeto_led_ativo = "PCI_640"
        self.config_repository = FakeRepository(leds)
        self._mask_guard_lock = RLock()
        self._mask_guard_project = ""
        self._mask_guard_snapshot = ()
        self._mask_resolution_active = (1280, 720)
        width, height = frame_resolution
        self.camera_frame_atual = np.zeros((height, width, 3), dtype=np.uint8)
        self.largura_original = width
        self.altura_original = height
        self.leds_fixos_configurados = []
        self.source_seen_by_sync = []

    def _obter_resolucao_mestra_projeto(self, projeto=None):
        if str(projeto or "") == "PCI_640":
            return (640, 480)
        return None

    def _mask_guard_active_project(self):
        return "PCI_640"

    def _mask_guard_current_resolution(self):
        height, width = self.camera_frame_atual.shape[:2]
        return (width, height)

    @staticmethod
    def _mask_guard_canonicalize(leds, reference_resolution):
        if reference_resolution is None:
            return copiar_mascaras_absolutas(leds)
        width, height = reference_resolution
        result = []
        for led in leds or ():
            canonical, _ = canonicalize_led_mask(
                led,
                reference_width=width,
                reference_height=height,
            )
            result.append(canonical)
        return result

    def _mask_guard_read_repository(self):
        return self.config_repository.carregar_leds_fixos("PCI_640")

    def _mask_guard_snapshot_copy(self):
        return copiar_mascaras_absolutas(self._mask_guard_snapshot)

    def _mask_guard_editing(self):
        return False

    def _mask_guard_enforce(self):
        return self._mask_guard_snapshot_copy()

    def _synchronize_masks_with_current_frame(
        self,
        force=False,
        schedule_operation_prepare=True,
    ):
        self.source_seen_by_sync = copiar_mascaras_absolutas(
            self.leds_fixos_configurados
        )

    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        width, height = self._mask_guard_current_resolution()
        return list(
            adapt_led_masks_to_resolution(
                leds_fixos,
                target_width=width,
                target_height=height,
                reference_width=640,
                reference_height=480,
            ).adapted_leds
        )

    def carregar_leds_fixos(self):
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos(
            "PCI_640"
        )


class DummyApp(ProjectMaskGeometryAnchorMixin, DummyBase):
    pass


class ProjectMaskGeometryAnchorTests(unittest.TestCase):
    @staticmethod
    def _freeform_640():
        return LedSelection(
            id="SEG_001",
            centro_x=320,
            centro_y=240,
            raio=2,
            tipo_roi="segmento",
            pontos_segmento_livre=[
                (-30.0, -10.0),
                (20.0, -10.0),
                (35.0, 15.0),
                (-25.0, 20.0),
            ],
        ).com_normalizacao(640, 480)

    def test_projeto_640_restaura_fonte_canonica_depois_de_frame_temporario(self):
        canonical = self._freeform_640()
        temporary = adapt_led_masks_to_resolution(
            [canonical],
            target_width=1280,
            target_height=720,
        ).adapted_leds[0]
        self.assertNotEqual(
            canonical.pontos_segmento_livre,
            temporary.pontos_segmento_livre,
        )

        app = DummyApp([canonical], frame_resolution=(640, 480))
        app.leds_fixos_configurados = [temporary]
        app._mask_resolution_active = (1280, 720)

        app._synchronize_masks_with_current_frame()

        self.assertEqual(1, len(app.source_seen_by_sync))
        source = app.source_seen_by_sync[0]
        self.assertEqual((320, 240), (source.centro_x, source.centro_y))
        self.assertEqual(
            canonical.pontos_segmento_livre,
            source.pontos_segmento_livre,
        )

    def test_voltar_para_640_reconstroi_segmento_exatamente_do_salvo(self):
        canonical = self._freeform_640()
        app = DummyApp([canonical], frame_resolution=(640, 480))

        app._mask_guard_capture(force=True, project="PCI_640")
        source = app._mask_guard_snapshot_copy()[0]
        restored = adapt_led_masks_to_resolution(
            [source],
            target_width=640,
            target_height=480,
            reference_width=640,
            reference_height=480,
        ).adapted_leds[0]

        self.assertEqual((320, 240), (restored.centro_x, restored.centro_y))
        self.assertEqual(canonical.largura, restored.largura)
        self.assertEqual(canonical.altura, restored.altura)
        self.assertEqual(
            canonical.pontos_segmento_livre,
            restored.pontos_segmento_livre,
        )

    def test_roi_legada_usa_resolucao_mestra_e_nao_frame_temporario(self):
        legacy = LedSelection(
            id="LED_001",
            centro_x=320,
            centro_y=240,
            raio=12,
        )
        app = DummyApp([legacy], frame_resolution=(1280, 720))

        app._mask_guard_capture(force=True, project="PCI_640")
        canonical = app._mask_guard_snapshot_copy()[0]

        self.assertTrue(canonical.possui_coordenadas_normalizadas())
        self.assertEqual((640, 480), (canonical.largura_base, canonical.altura_base))
        self.assertAlmostEqual(0.5, canonical.centro_x_normalizado, places=6)
        self.assertAlmostEqual(0.5, canonical.centro_y_normalizado, places=6)

    def test_sessao_neutra_nao_captura_ultimo_projeto_persistido(self):
        canonical = self._freeform_640()
        app = DummyApp([canonical])
        app._projeto_led_sessao_carregado = ""

        app._mask_guard_capture(force=True)

        self.assertEqual("__SESSION_EMPTY__", app._mask_guard_project)
        self.assertEqual((), app._mask_guard_snapshot)

    def test_ancora_nao_depende_do_display_f3(self):
        import src.platform.project_mask_geometry_anchor as module

        source = inspect.getsource(module)
        self.assertNotIn("DisplayProductionF3Window", source)
        self.assertNotIn("DisplayAutomaticCheckF3Mixin", source)
        self.assertIn("resolução mestre", source)


if __name__ == "__main__":
    unittest.main()
