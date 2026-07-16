#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

import cv2

from src.platform.linux_camera_backend import (
    construir_candidatos_linux,
    descobrir_dispositivos_video,
    opencv_tem_gstreamer,
)
from src.platform.raspberry_pi3_settings import (
    CAMERA_FPS,
    CAMERA_HEIGHT,
    CAMERA_RESOLUTION_FALLBACKS,
    CAMERA_WIDTH,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico do backend de câmera usado pelo ODIN no Linux."
    )
    parser.add_argument("--testar", action="store_true")
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()

    print(f"Python: {sys.version.split()[0]}")
    print(f"OpenCV: {cv2.__version__}")
    print(f"OpenCV path: {cv2.__file__}")
    print(f"GStreamer no OpenCV: {opencv_tem_gstreamer()}")
    print(
        f"Resolução preferida: {CAMERA_WIDTH}x{CAMERA_HEIGHT} "
        f"@ {CAMERA_FPS} FPS"
    )

    dispositivos = descobrir_dispositivos_video(0, None, 7)
    print("Dispositivos:")
    for caminho, indice in dispositivos:
        print(f"  - {caminho} (índice {indice})")

    candidatos = construir_candidatos_linux(
        dispositivos,
        largura=CAMERA_WIDTH,
        altura=CAMERA_HEIGHT,
        fps=CAMERA_FPS,
        gstreamer_disponivel=opencv_tem_gstreamer(),
        resolucoes_preferidas=CAMERA_RESOLUTION_FALLBACKS,
    )
    print("Pipelines disponíveis:")
    for posicao, candidato in enumerate(candidatos, start=1):
        resolucao = (
            f"{candidato.largura}x{candidato.altura}"
            if candidato.largura > 0 and candidato.altura > 0
            else "negociação automática"
        )
        print(
            f"  {posicao}. {candidato.nome} | "
            f"{candidato.dispositivo} | {candidato.formato} | "
            f"{resolucao}"
        )

    if not args.testar:
        return 0

    total_frames = max(1, int(args.frames))
    for candidato in candidatos:
        print(
            f"\nTestando {candidato.nome} em "
            f"{candidato.dispositivo}..."
        )
        inicio = time.perf_counter()
        try:
            capture = cv2.VideoCapture(
                candidato.origem,
                candidato.backend,
            )
        except Exception as erro:
            print(
                f"  erro ao abrir: "
                f"{type(erro).__name__}: {erro}"
            )
            continue

        if capture is None or not capture.isOpened():
            print("  não abriu")
            if capture is not None:
                capture.release()
            continue

        if candidato.tipo == "v4l2":
            try:
                capture.set(
                    cv2.CAP_PROP_FOURCC,
                    cv2.VideoWriter_fourcc(
                        *("MJPG" if candidato.formato == "MJPG" else "YUYV")
                    ),
                )
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, candidato.largura)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, candidato.altura)
                capture.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
            except Exception:
                pass

        validos = 0
        resolucao = None
        for _ in range(total_frames):
            sucesso, frame = capture.read()
            if (
                sucesso
                and frame is not None
                and getattr(frame, "size", 0) > 0
            ):
                validos += 1
                resolucao = (frame.shape[1], frame.shape[0])
        duracao = max(0.0001, time.perf_counter() - inicio)
        capture.release()
        print(
            f"  frames válidos: {validos}/{total_frames} | "
            f"FPS medido: {validos / duracao:.2f} | "
            f"resolução real: {resolucao}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
