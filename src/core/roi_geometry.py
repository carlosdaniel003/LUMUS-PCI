from __future__ import annotations

import math
from typing import Iterable

import cv2
import numpy as np


TIPO_ROI_CIRCULO = "circulo"
TIPO_ROI_SEGMENTO = "segmento"
TIPOS_ROI = (TIPO_ROI_SEGMENTO, TIPO_ROI_CIRCULO)

SEGMENTO_LARGURA_PADRAO = 48
SEGMENTO_ALTURA_PADRAO = 14
SEGMENTO_LARGURA_MINIMA = 8
SEGMENTO_ALTURA_MINIMA = 4


def normalizar_tipo_roi(valor) -> str:
    texto = str(valor or TIPO_ROI_CIRCULO).strip().lower()
    if texto in {"segmento", "segment", "barra", "bar"}:
        return TIPO_ROI_SEGMENTO
    return TIPO_ROI_CIRCULO


def normalizar_angulo_segmento(valor) -> float:
    try:
        angulo = float(valor) % 360.0
    except (TypeError, ValueError):
        return 0.0
    if angulo > 180.0:
        angulo -= 360.0
    return float(angulo)


def dimensoes_segmento(alvo) -> tuple[int, int]:
    largura = getattr(alvo, "largura", None)
    altura = getattr(alvo, "altura", None)
    raio = max(1, int(getattr(alvo, "raio", 1) or 1))

    try:
        largura = int(largura)
    except (TypeError, ValueError):
        largura = max(SEGMENTO_LARGURA_PADRAO, raio * 2)

    try:
        altura = int(altura)
    except (TypeError, ValueError):
        altura = max(SEGMENTO_ALTURA_PADRAO, int(round(raio * 0.65)))

    return (
        max(SEGMENTO_LARGURA_MINIMA, largura),
        max(SEGMENTO_ALTURA_MINIMA, altura),
    )


def raio_compatibilidade_segmento(largura: int, altura: int) -> int:
    return max(
        2,
        int(
            math.ceil(
                math.hypot(
                    max(1, int(largura)) / 2.0,
                    max(1, int(altura)) / 2.0,
                )
            )
        ),
    )


def _pontos_segmento_local(largura: int, altura: int) -> np.ndarray:
    largura = max(SEGMENTO_LARGURA_MINIMA, int(largura))
    altura = max(SEGMENTO_ALTURA_MINIMA, int(altura))
    meia_largura = largura / 2.0
    meia_altura = altura / 2.0
    chanfro = min(
        meia_altura * 0.72,
        largura * 0.12,
    )

    return np.array(
        [
            (-meia_largura + chanfro, -meia_altura),
            (meia_largura - chanfro, -meia_altura),
            (meia_largura, -meia_altura + chanfro),
            (meia_largura, meia_altura - chanfro),
            (meia_largura - chanfro, meia_altura),
            (-meia_largura + chanfro, meia_altura),
            (-meia_largura, meia_altura - chanfro),
            (-meia_largura, -meia_altura + chanfro),
        ],
        dtype=np.float32,
    )


def pontos_segmento(
    alvo,
    escala: float = 1.0,
) -> np.ndarray:
    largura, altura = dimensoes_segmento(alvo)
    escala = max(0.05, float(escala))
    locais = _pontos_segmento_local(
        max(SEGMENTO_LARGURA_MINIMA, int(round(largura * escala))),
        max(SEGMENTO_ALTURA_MINIMA, int(round(altura * escala))),
    )

    angulo = math.radians(
        normalizar_angulo_segmento(getattr(alvo, "angulo", 0.0))
    )
    cos_a = math.cos(angulo)
    sin_a = math.sin(angulo)
    matriz = np.array(
        [[cos_a, -sin_a], [sin_a, cos_a]],
        dtype=np.float32,
    )
    rotacionados = locais @ matriz.T
    rotacionados[:, 0] += float(getattr(alvo, "centro_x", 0))
    rotacionados[:, 1] += float(getattr(alvo, "centro_y", 0))
    return rotacionados


def bbox_roi(alvo) -> tuple[int, int, int, int]:
    if normalizar_tipo_roi(getattr(alvo, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        pontos = pontos_segmento(alvo)
        x1 = int(math.floor(float(np.min(pontos[:, 0]))))
        y1 = int(math.floor(float(np.min(pontos[:, 1]))))
        x2 = int(math.ceil(float(np.max(pontos[:, 0]))))
        y2 = int(math.ceil(float(np.max(pontos[:, 1]))))
        return x1, y1, x2, y2

    raio = max(1, int(getattr(alvo, "raio", 1) or 1))
    centro_x = int(getattr(alvo, "centro_x", 0))
    centro_y = int(getattr(alvo, "centro_y", 0))
    return (
        centro_x - raio,
        centro_y - raio,
        centro_x + raio,
        centro_y + raio,
    )


def roi_dentro_imagem(alvo, largura: int, altura: int) -> bool:
    if int(largura) <= 0 or int(altura) <= 0:
        return False
    x1, y1, x2, y2 = bbox_roi(alvo)
    return (
        x1 >= 0
        and y1 >= 0
        and x2 < int(largura)
        and y2 < int(altura)
    )


def ponto_dentro_roi(alvo, x: float, y: float) -> bool:
    if normalizar_tipo_roi(getattr(alvo, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        poligono = pontos_segmento(alvo).astype(np.float32)
        return cv2.pointPolygonTest(
            poligono,
            (float(x), float(y)),
            False,
        ) >= 0

    dx = float(x) - float(getattr(alvo, "centro_x", 0))
    dy = float(y) - float(getattr(alvo, "centro_y", 0))
    raio = max(1, int(getattr(alvo, "raio", 1) or 1))
    return dx * dx + dy * dy <= raio * raio


def criar_mascara_roi_global(
    alvo,
    largura: int,
    altura: int,
    escala: float = 1.0,
) -> np.ndarray:
    mascara = np.zeros((int(altura), int(largura)), dtype=np.uint8)
    if normalizar_tipo_roi(getattr(alvo, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        poligono = np.rint(pontos_segmento(alvo, escala=escala)).astype(np.int32)
        cv2.fillConvexPoly(mascara, poligono, 255)
        return mascara

    centro = (
        int(getattr(alvo, "centro_x", 0)),
        int(getattr(alvo, "centro_y", 0)),
    )
    raio = max(
        1,
        int(round(int(getattr(alvo, "raio", 1) or 1) * float(escala))),
    )
    cv2.circle(mascara, centro, raio, 255, -1)
    return mascara


def _mascaras_segmento_locais(alvo, x1: int, y1: int, x2: int, y2: int):
    altura_roi = max(1, int(y2 - y1))
    largura_roi = max(1, int(x2 - x1))
    principal = np.zeros((altura_roi, largura_roi), dtype=np.uint8)

    poligono = pontos_segmento(alvo).copy()
    poligono[:, 0] -= float(x1)
    poligono[:, 1] -= float(y1)
    cv2.fillConvexPoly(
        principal,
        np.rint(poligono).astype(np.int32),
        255,
    )

    largura_segmento, altura_segmento = dimensoes_segmento(alvo)
    espessura = max(1, int(round(min(largura_segmento, altura_segmento) * 0.18)))
    kernel_interno = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (espessura * 2 + 1, espessura * 2 + 1),
    )
    interno = cv2.erode(principal, kernel_interno, iterations=1)
    if not np.any(interno):
        interno = principal.copy()

    espessura_anel = max(1, int(round(min(largura_segmento, altura_segmento) * 0.28)))
    kernel_anel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (espessura_anel * 2 + 1, espessura_anel * 2 + 1),
    )
    nucleo_anel = cv2.erode(principal, kernel_anel, iterations=1)
    anel = cv2.bitwise_and(principal, cv2.bitwise_not(nucleo_anel))
    if not np.any(anel):
        anel = principal.copy()

    return principal > 0, interno > 0, anel > 0


def criar_mascaras_roi(
    alvo,
    largura_frame: int,
    altura_frame: int,
):
    """Retorna bbox exclusiva e máscaras booleanas localizadas na ROI."""
    largura_frame = int(largura_frame)
    altura_frame = int(altura_frame)
    if largura_frame <= 0 or altura_frame <= 0:
        return None

    tipo = normalizar_tipo_roi(getattr(alvo, "tipo_roi", None))
    if tipo == TIPO_ROI_SEGMENTO:
        bx1, by1, bx2, by2 = bbox_roi(alvo)
        x1 = max(0, bx1 - 1)
        y1 = max(0, by1 - 1)
        x2 = min(largura_frame, bx2 + 2)
        y2 = min(altura_frame, by2 + 2)
        if x2 <= x1 or y2 <= y1:
            return None
        principal, interna, anel = _mascaras_segmento_locais(
            alvo, x1, y1, x2, y2
        )
        return x1, y1, x2, y2, principal, interna, anel

    centro_x = int(getattr(alvo, "centro_x", 0))
    centro_y = int(getattr(alvo, "centro_y", 0))
    raio = max(2, int(getattr(alvo, "raio", 2) or 2))
    x1 = max(0, centro_x - raio)
    y1 = max(0, centro_y - raio)
    x2 = min(largura_frame, centro_x + raio + 1)
    y2 = min(altura_frame, centro_y + raio + 1)
    if x2 <= x1 or y2 <= y1:
        return None

    yy, xx = np.ogrid[: y2 - y1, : x2 - x1]
    local_x = centro_x - x1
    local_y = centro_y - y1
    distancia = (xx - local_x) ** 2 + (yy - local_y) ** 2
    raio_interno = max(2, int(raio * 0.45))
    raio_anel_interno = max(raio_interno + 1, int(raio * 0.62))
    principal = distancia <= raio**2
    interna = distancia <= raio_interno**2
    anel = (distancia >= raio_anel_interno**2) & (distancia <= raio**2)
    return x1, y1, x2, y2, principal, interna, anel


def todos_pontos_dentro_area(
    alvo,
    esquerda: int,
    topo: int,
    direita: int,
    base: int,
) -> bool:
    x1, y1, x2, y2 = bbox_roi(alvo)
    return (
        x1 >= int(esquerda)
        and y1 >= int(topo)
        and x2 <= int(direita)
        and y2 <= int(base)
    )
