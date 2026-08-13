from __future__ import annotations

from typing import Iterable

from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.models.led_selection import LedSelection


_PATCH_SEGMENTO_LIVRE_PERSISTENCIA = False


def copiar_mascara_absoluta_segmento_livre(led: LedSelection) -> LedSelection:
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def copiar_led_geometria_completa_segmento_livre(
    led: LedSelection,
) -> LedSelection:
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        centro_x_normalizado=led.centro_x_normalizado,
        centro_y_normalizado=led.centro_y_normalizado,
        raio_normalizado=led.raio_normalizado,
        largura_base=led.largura_base,
        altura_base=led.altura_base,
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def assinatura_geometria_segmento_livre(
    leds: Iterable[LedSelection] | None,
) -> tuple[tuple, ...]:
    assinatura = []
    for led in leds or ():
        tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))
        if tipo == TIPO_ROI_SEGMENTO:
            pontos = tuple(
                (round(float(x), 4), round(float(y), 4))
                for x, y in (
                    getattr(led, "pontos_segmento_livre", None) or ()
                )
            )
            assinatura.append(
                (
                    str(led.id),
                    TIPO_ROI_SEGMENTO,
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                    None if getattr(led, "largura", None) is None else int(led.largura),
                    None if getattr(led, "altura", None) is None else int(led.altura),
                    round(float(getattr(led, "angulo", 0.0) or 0.0), 6),
                    pontos,
                )
            )
        else:
            assinatura.append(
                (
                    str(led.id),
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                )
            )
    return tuple(assinatura)


def instalar_persistencia_segmento_livre() -> None:
    global _PATCH_SEGMENTO_LIVRE_PERSISTENCIA
    if _PATCH_SEGMENTO_LIVRE_PERSISTENCIA:
        return

    import src.platform.fixed_mask_geometry_guard as fixed_guard
    import src.platform.segment_project_geometry_persistence as persistence

    fixed_guard.copiar_mascara_absoluta = copiar_mascara_absoluta_segmento_livre
    fixed_guard.assinatura_geometria = assinatura_geometria_segmento_livre
    persistence.copiar_led_geometria_completa = copiar_led_geometria_completa_segmento_livre
    _PATCH_SEGMENTO_LIVRE_PERSISTENCIA = True
