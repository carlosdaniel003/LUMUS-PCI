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
    largura: int
    altura: int
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


def _normalizar_resolucoes(
    largura: int,
    altura: int,
    resolucoes_preferidas: tuple[tuple[int, int], ...] | None,
) -> tuple[tuple[int, int], ...]:
    resultado: list[tuple[int, int]] = []

    def adicionar(valor_largura: int, valor_altura: int) -> None:
        resolucao = (
            max(1, int(valor_largura)),
            max(1, int(valor_altura)),
        )
        if resolucao not in resultado:
            resultado.append(resolucao)

    adicionar(largura, altura)
    for item in resolucoes_preferidas or ():
        if len(item) >= 2:
            adicionar(item[0], item[1])

    for resolucao in (
        (3840, 2160),
        (2560, 1440),
        (1920, 1080),
        (1280, 720),
        (640, 480),
    ):
        if resolucao[0] <= int(largura) and resolucao[1] <= int(altura):
            adicionar(*resolucao)

    return tuple(resultado)


def construir_candidatos_linux(
    dispositivos: tuple[tuple[str, int | None], ...],
    largura: int,
    altura: int,
    fps: int,
    gstreamer_disponivel: bool,
    resolucoes_preferidas: tuple[tuple[int, int], ...] | None = None,
) -> tuple[LinuxCameraBackendCandidate, ...]:
    candidatos: list[LinuxCameraBackendCandidate] = []
    formatos = ("MJPG", "YUY2")
    resolucoes = _normalizar_resolucoes(
        largura,
        altura,
        resolucoes_preferidas,
    )

    if gstreamer_disponivel:
        for largura_atual, altura_atual in resolucoes:
            for dispositivo, indice in dispositivos:
                identificador = os.path.realpath(dispositivo)
                for formato in formatos:
                    pipeline = construir_pipeline_gstreamer(
                        dispositivo,
                        largura_atual,
                        altura_atual,
                        fps,
                        formato,
                    )
                    candidatos.append(
                        LinuxCameraBackendCandidate(
                            key=(
                                f"gstreamer:{identificador}:{formato}:"
                                f"{largura_atual}x{altura_atual}"
                            ),
                            nome=(
                                f"GStreamer {formato} "
                                f"{largura_atual}x{altura_atual}"
                            ),
                            tipo="gstreamer",
                            origem=pipeline,
                            backend=cv2.CAP_GSTREAMER,
                            dispositivo=dispositivo,
                            formato=formato,
                            largura=largura_atual,
                            altura=altura_atual,
                            indice=indice,
                        )
                    )

    indices_vistos: set[int] = set()
    dispositivos_por_indice: list[tuple[str, int]] = []
    for dispositivo, indice in dispositivos:
        if indice is None or indice in indices_vistos:
            continue
        indices_vistos.add(indice)
        dispositivos_por_indice.append((dispositivo, indice))

    for largura_atual, altura_atual in resolucoes:
        for dispositivo, indice in dispositivos_por_indice:
            for formato in formatos:
                candidatos.append(
                    LinuxCameraBackendCandidate(
                        key=(
                            f"v4l2:{indice}:{formato}:"
                            f"{largura_atual}x{altura_atual}"
                        ),
                        nome=(
                            f"V4L2 {formato} "
                            f"{largura_atual}x{altura_atual}"
                        ),
                        tipo="v4l2",
                        origem=indice,
                        backend=cv2.CAP_V4L2,
                        dispositivo=dispositivo,
                        formato=formato,
                        largura=largura_atual,
                        altura=altura_atual,
                        indice=indice,
                    )
                )

    for dispositivo, indice in dispositivos_por_indice:
        candidatos.append(
            LinuxCameraBackendCandidate(
                key=f"auto:{indice}",
                nome="Backend automático",
                tipo="auto",
                origem=indice,
                backend=cv2.CAP_ANY,
                dispositivo=dispositivo,
                formato="AUTO",
                largura=0,
                altura=0,
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
