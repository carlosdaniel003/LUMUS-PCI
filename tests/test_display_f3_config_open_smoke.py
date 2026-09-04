from __future__ import annotations

import tempfile
import tkinter as tk
import traceback
import unittest
from pathlib import Path

from src.platform.display_project_repository import DisplayProjectRepository
from src.platform.display_visual_reference_status import instalar_status_referencias_visuais_display
from src.platform.display_reference_roi import instalar_roi_referencias_display_f3
from src.platform.display_f3_fast_expected_gate import instalar_gate_rapido_check_esperado_display_f3
import src.platform.display_production_f3 as production_module


class DisplayF3ConfigOpenSmokeTests(unittest.TestCase):
    def test_final_config_window_opens_with_real_tk(self):
        root = tk.Tk()
        root.withdraw()
        created = None
        try:
            instalar_status_referencias_visuais_display()
            instalar_roi_referencias_display_f3()
            instalar_gate_rapido_check_esperado_display_f3()

            with tempfile.TemporaryDirectory() as directory:
                repository = DisplayProjectRepository(Path(directory) / "display.json")
                try:
                    created = production_module.DisplayProjectConfigWindow(
                        root=root,
                        repository=repository,
                        frame_provider=lambda: None,
                        on_change=lambda: None,
                        on_close=lambda: None,
                    )
                    root.update_idletasks()
                    root.update()
                except Exception:
                    traceback.print_exc()
                    raise

                self.assertTrue(created.visible)
                self.assertIs(created.repository, repository)
        finally:
            if created is not None:
                try:
                    created.close()
                except Exception:
                    pass
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
