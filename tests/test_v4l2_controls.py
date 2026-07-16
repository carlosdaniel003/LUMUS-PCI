import subprocess
import unittest
from unittest.mock import patch

from src.platform.v4l2_controls import V4L2ControlManager


class FakeRunner:
    def __init__(self):
        self.chamadas = []

    def __call__(self, comando, **kwargs):
        self.chamadas.append(comando)
        ultimo = comando[-1]
        if ultimo.startswith("--get-ctrl=exposure_absolute"):
            saida = "exposure_absolute: 120"
        elif ultimo.startswith("--get-ctrl=focus_absolute"):
            saida = "focus_absolute: 35"
        elif ultimo.startswith(
            "--get-ctrl=white_balance_temperature"
        ):
            saida = "white_balance_temperature: 4500"
        else:
            saida = ""
        return subprocess.CompletedProcess(
            comando,
            0,
            stdout=saida,
            stderr="",
        )


class V4L2ControlManagerTests(unittest.TestCase):
    def test_congela_valores_automaticos_atuais(self):
        runner = FakeRunner()
        with patch(
            "src.platform.v4l2_controls.shutil.which",
            return_value="/usr/bin/v4l2-ctl",
        ):
            manager = V4L2ControlManager(
                "/dev/video0",
                runner=runner,
            )
            resultados = manager.congelar_automaticos(
                {
                    "exposure_auto": True,
                    "focus_auto": True,
                    "white_balance_auto": True,
                }
            )

        comandos = [item[-1] for item in runner.chamadas]
        self.assertIn("--set-ctrl=exposure_auto=1", comandos)
        self.assertIn(
            "--set-ctrl=exposure_absolute=120",
            comandos,
        )
        self.assertIn("--set-ctrl=focus_auto=0", comandos)
        self.assertIn("--set-ctrl=focus_absolute=35", comandos)
        self.assertIn(
            "--set-ctrl=white_balance_temperature_auto=0",
            comandos,
        )
        self.assertIn(
            "--set-ctrl=white_balance_temperature=4500",
            comandos,
        )
        self.assertTrue(resultados["exposure_auto"].aplicado)


if __name__ == "__main__":
    unittest.main()
