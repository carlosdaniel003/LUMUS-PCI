from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re

import cv2


@dataclass(frozen=True)
class LinuxCameraBackendCandidate:
    key: str
    nome: str
    tipo: str
    origem: str | int
    backend: int
    dispositivo: str
    formato: str
    indice: int | None = None


def opencv_tem_gstreamer(build_info: str | None = None) -> bool:
    if build_info is None:
        try:
            build_info = cv2.getBuildInformation()
        except Exception:
            return False

    return bool(
        re.search(
            r"^\s*GStreamer\s*:\s*YES\b",
            str(build_info),
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )


def _indice_video(caminho: str) -> int | None:
    nome = os.path.basename(os.path.realpath(caminho))
    correspondencia = re.fullmatch(r"video(\d+)", nome)
    return int(correspondencia.group(1)) if correspondencia else None


def descobrir_dispositivos_video(
    indice_solicitado: int,
    indice_ativo: int | None,
    indice_maximo: int,
    diretorio_by_id: str = "/dev/v4l/by-id",
) -> tuple[tuple[str, int | None], ...]:
    dispositivos: list[tuple[str, int | None]] = []
    vistos_reais: set[str] = set()

    def adicionar(caminho: str, indice: int | None = None) -> None:
        real = os.path.realpath(caminho)
        if real in vistos_reais:
            return
        if not os.path.exists(caminho) and not os.path.exists(real):
            return
        vistos_reais.add(real)
        dispositivos.append(
            (
                caminho,
                indice if indice is not None else _indice_video(caminho),
            )
        )

    pasta = Path(diretorio_by_id)
    if pasta.is_dir():
        links = sorted(
            pasta.glob("*video-index0"),
            key=lambda item: item.name,
        )
        for link in links:
            adicionar(str(link))

    indices: list[int] = []
    for indice in (indice_ativo, indice_solicitado):
        if (
            indice is not None
            and int(indice) >= 0
            and int(indice) not in indices
        ):
            indices.append(int(indice))
    for indice in range(max(0, int(indice_maximo)) + 1):
        if indice not in indices:
            indices.append(indice)

    for indice in indices:
        adicionar(f"/dev/video{indice}", indice)

    return tuple(dispositivos)


def _escapar_dispositivo_gstreamer(dispositivo: str) -> str:
    return (
        str(dispositivo)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def construir_pipeline_gstreamer(
    dispositivo: str,
    largura: int,
    altura: int,
    fps: int,
    formato: str,
) -> str:
    dispositivo = _escapar_dispositivo_gstreamer(dispositivo)
    largura = max(1, int(largura))
    altura = max(1, int(altura))
    fps = max(1, int(fps))
    formato = str(formato).upper()

    origem = f'v4l2src device="{dispositivo}" do-timestamp=true'
    fila = "queue leaky=downstream max-size-buffers=1"
    destino = (
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )

    if formato == "MJPG":
        caps = (
            f"image/jpeg,width={largura},height={altura},"
            f"framerate={fps}/1"
        )
        return f"{origem} ! {caps} ! {fila} ! jpegdec ! {destino}"

    caps = (
        f"video/x-raw,format=YUY2,width={largura},height={altura},"
        f"framerate={fps}/1"
    )
    return f"{origem} ! {caps} ! {fila} ! {destino}"


def construir_candidatos_linux(
    dispositivos: tuple[tuple[str, int | None], ...],
    largura: int,
    altura: int,
    fps: int,
    gstreamer_disponivel: bool,
) -> tuple[LinuxCameraBackendCandidate, ...]:
    candidatos: list[LinuxCameraBackendCandidate] = []
    formatos = ("MJPG", "YUY2")

    for dispositivo, indice in dispositivos:
        identificador = os.path.realpath(dispositivo)
        if gstreamer_disponivel:
            for formato in formatos:
                pipeline = construir_pipeline_gstreamer(
                    dispositivo,
                    largura,
                    altura,
                    fps,
                    formato,
                )
                candidatos.append(
                    LinuxCameraBackendCandidate(
                        key=f"gstreamer:{identificador}:{formato}",
                        nome=f"GStreamer {formato}",
                        tipo="gstreamer",
                        origem=pipeline,
                        backend=cv2.CAP_GSTREAMER,
                        dispositivo=dispositivo,
                        formato=formato,
                        indice=indice,
                    )
                )

    indices_vistos: set[int] = set()
    for dispositivo, indice in dispositivos:
        if indice is None or indice in indices_vistos:
            continue
        indices_vistos.add(indice)
        for formato in formatos:
            candidatos.append(
                LinuxCameraBackendCandidate(
                    key=f"v4l2:{indice}:{formato}",
                    nome=f"V4L2 {formato}",
                    tipo="v4l2",
                    origem=indice,
                    backend=cv2.CAP_V4L2,
                    dispositivo=dispositivo,
                    formato=formato,
                    indice=indice,
                )
            )

    for dispositivo, indice in dispositivos:
        if indice is None:
            continue
        candidatos.append(
            LinuxCameraBackendCandidate(
                key=f"auto:{indice}",
                nome="Backend automático",
                tipo="auto",
                origem=indice,
                backend=cv2.CAP_ANY,
                dispositivo=dispositivo,
                formato="AUTO",
                indice=indice,
            )
        )

    unicos: list[LinuxCameraBackendCandidate] = []
    chaves: set[str] = set()
    for candidato in candidatos:
        if candidato.key not in chaves:
            chaves.add(candidato.key)
            unicos.append(candidato)
    return tuple(unicos)
