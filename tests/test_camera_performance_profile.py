import unittest

from src.platform.camera_performance_profile import (
    calculate_camera_performance,
    select_best_camera_performance,
)


def timestamps_for_fps(fps: float, count: int = 16) -> list[float]:
    return [index / float(fps) for index in range(count)]


def stable_result(
    key: str,
    width: int,
    height: int,
    fps: float,
    brightness=None,
):
    count = 16
    return calculate_camera_performance(
        candidate_key=key,
        width=width,
        height=height,
        timestamps=timestamps_for_fps(fps, count),
        valid_flags=[True] * count,
        corrupted_flags=[False] * count,
        brightness_values=(
            list(brightness)
            if brightness is not None
            else [120.0] * count
        ),
        target_fps=30.0,
        target_resolution=(1920, 1080),
    )


class CameraPerformanceProfileTests(unittest.TestCase):
    def test_4k_so_ganha_quando_excelente(self):
        full_hd = stable_result("1080", 1920, 1080, 30.0)
        uhd_lento = stable_result("4k", 3840, 2160, 25.0)

        escolhido = select_best_camera_performance(
            (full_hd, uhd_lento),
            target_resolution=(1920, 1080),
        )

        self.assertEqual("1080", escolhido.candidate_key)
        self.assertTrue(full_hd.excellent)
        self.assertFalse(uhd_lento.excellent)

    def test_maior_resolucao_excelente_supera_1080p(self):
        full_hd = stable_result("1080", 1920, 1080, 30.0)
        qhd = stable_result("1440", 2560, 1440, 29.5)

        escolhido = select_best_camera_performance(
            (full_hd, qhd),
            target_resolution=(1920, 1080),
        )

        self.assertEqual("1440", escolhido.candidate_key)
        self.assertTrue(qhd.excellent)

    def test_desce_para_720p_quando_1080p_nao_esta_confortavel(self):
        full_hd_instavel = calculate_camera_performance(
            candidate_key="1080",
            width=1920,
            height=1080,
            timestamps=timestamps_for_fps(18.0),
            valid_flags=[True] * 16,
            corrupted_flags=[False] * 16,
            brightness_values=[120.0] * 16,
            target_fps=30.0,
            target_resolution=(1920, 1080),
        )
        hd = stable_result("720", 1280, 720, 29.0)

        escolhido = select_best_camera_performance(
            (full_hd_instavel, hd),
            target_resolution=(1920, 1080),
        )

        self.assertEqual("720", escolhido.candidate_key)
        self.assertFalse(full_hd_instavel.comfortable)
        self.assertTrue(hd.comfortable)

    def test_piscada_repetida_reprova_o_perfil(self):
        brightness = [80.0, 150.0] * 8
        resultado = stable_result(
            "flicker",
            1920,
            1080,
            30.0,
            brightness=brightness,
        )

        self.assertGreater(resultado.flicker_ratio, 0.18)
        self.assertFalse(resultado.comfortable)

    def test_frame_corrompido_reprova_o_perfil(self):
        count = 16
        resultado = calculate_camera_performance(
            candidate_key="bandas",
            width=1920,
            height=1080,
            timestamps=timestamps_for_fps(30.0, count),
            valid_flags=[True] * count,
            corrupted_flags=[False] * 15 + [True],
            brightness_values=[120.0] * count,
            target_fps=30.0,
            target_resolution=(1920, 1080),
        )

        self.assertGreater(resultado.corrupted_ratio, 0.02)
        self.assertFalse(resultado.comfortable)


if __name__ == "__main__":
    unittest.main()
