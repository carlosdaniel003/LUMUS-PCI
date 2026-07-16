import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.platform.linux_camera_backend import (
    construir_candidatos_linux,
    construir_pipeline_gstreamer,
    descobrir_dispositivos_video,
    opencv_tem_gstreamer,
)


class LinuxCameraBackendTests(unittest.TestCase):
    def test_detecta_gstreamer_no_build_info(self):
        self.assertTrue(
            opencv_tem_gstreamer(
                "Video I/O:\n    GStreamer: YES (1.22)"
            )
        )
        self.assertFalse(
            opencv_tem_gstreamer(
                "Video I/O:\n    GStreamer: NO"
            )
        )

    def test_pipeline_mjpg_descarta_frames_atrasados(self):
        pipeline = construir_pipeline_gstreamer(
            "/dev/video0",
            640,
            480,
            30,
            "MJPG",
        )
        self.assertIn("image/jpeg", pipeline)
        self.assertIn("jpegdec", pipeline)
        self.assertIn("drop=true", pipeline)
        self.assertIn("max-buffers=1", pipeline)
        self.assertIn("sync=false", pipeline)

    def test_pipeline_yuy2_nao_usa_decoder_jpeg(self):
        pipeline = construir_pipeline_gstreamer(
            "/dev/video2",
            640,
            480,
            30,
            "YUY2",
        )
        self.assertIn("format=YUY2", pipeline)
        self.assertNotIn("jpegdec", pipeline)

    def test_candidatos_priorizam_gstreamer_e_mantem_fallback(self):
        candidatos = construir_candidatos_linux(
            (("/dev/video0", 0),),
            640,
            480,
            30,
            gstreamer_disponivel=True,
        )
        self.assertEqual("gstreamer", candidatos[0].tipo)
        self.assertEqual("MJPG", candidatos[0].formato)
        self.assertTrue(
            any(item.tipo == "v4l2" for item in candidatos)
        )
        self.assertTrue(
            any(item.tipo == "auto" for item in candidatos)
        )

    def test_descoberta_prefere_link_estavel_sem_duplicar_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raiz = Path(temp_dir)
            dev = raiz / "dev"
            by_id = dev / "v4l" / "by-id"
            by_id.mkdir(parents=True)
            video0 = dev / "video0"
            video0.touch()
            link = by_id / "usb-camera-video-index0"
            link.symlink_to(video0)

            def existe(caminho):
                texto = str(caminho)
                if texto == "/dev/video0":
                    return True
                return Path(texto).exists()

            realpath_original = __import__("os").path.realpath

            def realpath(caminho, *args, **kwargs):
                if str(caminho) == "/dev/video0":
                    return str(video0)
                return realpath_original(
                    caminho,
                    *args,
                    **kwargs,
                )

            with patch(
                "src.platform.linux_camera_backend.os.path.exists",
                side_effect=existe,
            ), patch(
                "src.platform.linux_camera_backend.os.path.realpath",
                side_effect=realpath,
            ):
                dispositivos = descobrir_dispositivos_video(
                    0,
                    None,
                    0,
                    diretorio_by_id=str(by_id),
                )

            self.assertEqual(1, len(dispositivos))
            self.assertEqual(str(link), dispositivos[0][0])


if __name__ == "__main__":
    unittest.main()
