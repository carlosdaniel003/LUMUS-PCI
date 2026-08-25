from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from linux_local_config_bootstrap import (
    ODIN_CONFIG_DIR_ENV,
    ODIN_CONFIG_FILENAME,
    preparar_configuracao_local_linux,
)


class LinuxLocalConfigBootstrapTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_first_run_copies_legacy_config_and_rewrites_reference_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "ODIN"
            legacy = project / "data" / "config"
            home = root / "home"
            sample = legacy / "roi_samples" / "LED_001_aceso.png"
            sample.parent.mkdir(parents=True, exist_ok=True)
            sample.write_bytes(b"sample")
            legacy_config = legacy / ODIN_CONFIG_FILENAME
            self._write_json(
                legacy_config,
                {
                    "led_projects": {
                        "P": {
                            "fixed_leds": [{"id": "LED_001", "centro_x": 123}],
                        }
                    },
                    "reference_on": {"image_path": str(sample.resolve())},
                },
            )
            env: dict[str, str] = {}

            local_dir = preparar_configuracao_local_linux(
                project,
                home=home,
                environment=env,
            )

            self.assertEqual(str(local_dir), env[ODIN_CONFIG_DIR_ENV])
            local_config = local_dir / ODIN_CONFIG_FILENAME
            self.assertTrue(local_config.exists())
            self.assertTrue((local_dir / "roi_samples" / sample.name).exists())
            migrated = json.loads(local_config.read_text(encoding="utf-8"))
            self.assertEqual(
                str((local_dir / "roi_samples" / sample.name).resolve()),
                migrated["reference_on"]["image_path"],
            )
            self.assertEqual(
                123,
                migrated["led_projects"]["P"]["fixed_leds"][0]["centro_x"],
            )

    def test_existing_local_geometry_is_never_overwritten_by_legacy_update(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "ODIN"
            legacy = project / "data" / "config"
            home = root / "home"
            env: dict[str, str] = {}

            self._write_json(
                legacy / ODIN_CONFIG_FILENAME,
                {"fixed_leds": [{"id": "LED_001", "centro_x": 100}]},
            )
            local_dir = preparar_configuracao_local_linux(
                project,
                home=home,
                environment=env,
            )
            local_config = local_dir / ODIN_CONFIG_FILENAME

            # Simula o operador corrigindo a máscara no JIG.
            self._write_json(
                local_config,
                {"fixed_leds": [{"id": "LED_001", "centro_x": 321}]},
            )

            # Simula um git pull/reset restaurando uma geometria antiga no repo.
            self._write_json(
                legacy / ODIN_CONFIG_FILENAME,
                {"fixed_leds": [{"id": "LED_001", "centro_x": 77}]},
            )
            preparar_configuracao_local_linux(
                project,
                home=home,
                environment=env,
            )

            persisted = json.loads(local_config.read_text(encoding="utf-8"))
            self.assertEqual(321, persisted["fixed_leds"][0]["centro_x"])

    def test_config_module_honors_external_config_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "odin-local"
            env = dict(os.environ)
            env[ODIN_CONFIG_DIR_ENV] = str(target)
            command = (
                "import config; "
                "print(config.CONFIG_DIR); "
                "print(config.CONFIG_FILE)"
            )
            completed = subprocess.run(
                [sys.executable, "-c", command],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            lines = completed.stdout.strip().splitlines()
            self.assertEqual(str(target), lines[0])
            self.assertEqual(str(target / ODIN_CONFIG_FILENAME), lines[1])


if __name__ == "__main__":
    unittest.main()
