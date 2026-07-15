from __future__ import annotations

from dataclasses import dataclass
import math
import time

import cv2
import numpy as np

from src.core.feature_extractor import extrair_features_led, validar_centro_led
from src.models.led_selection import LedSelection


MAX_AUTOMATIC_LEDS = 50
MAX_PROCESSING_DIMENSION = 1280

# Perfil rigoroso usado em imagens estáticas e capturas com boa resolução.
MIN_INNER_V_MEAN = 225.0
MIN_CENTER_TO_RING_V = 40.0
MIN_GLOW_SCORE = 112.0
MIN_RADIAL_BRIGHTNESS_RATIO = 1.20

# A câmera do Raspberry opera em 640x480 e pode entregar LEDs com brilho abaixo
# de 245 por causa da exposição. O perfil ao vivo relaxa somente os valores
# absolutos e preserva um contraste radial maior que o observado em J39/J40.
CAMERA_MIN_INNER_V_MEAN = 185.0
CAMERA_MIN_CENTER_TO_RING_V = 34.0
CAMERA_MIN_GLOW_SCORE = 78.0
CAMERA_MIN_RADIAL_BRIGHTNESS_RATIO = 1.14


@dataclass(frozen=True)
class AutomaticLedDetectionResult:
    leds: tuple[LedSelection, ...]
    candidate_count: int
    elapsed_seconds: float
    truncated: bool


def _matches_pattern(features, profile: str) -> bool:
    ring_v_mean = max(1.0, float(features.ring_v_mean))
    radial_brightness_ratio = float(features.inner_v_mean) / ring_v_mean

    if profile == "camera":
        has_compact_emissive_core = (
            features.inner_v_mean >= CAMERA_MIN_INNER_V_MEAN
            and features.center_to_ring_v >= CAMERA_MIN_CENTER_TO_RING_V
            and features.glow_score >= CAMERA_MIN_GLOW_SCORE
            and radial_brightness_ratio >= CAMERA_MIN_RADIAL_BRIGHTNESS_RATIO
        )
        return (
            features.v_max >= 225.0
            and features.v_p95 >= 205.0
            and features.percent_on >= 0.08
            and features.percent_hot_220 >= 0.02
            and has_compact_emissive_core
        )

    has_compact_emissive_core = (
        features.inner_v_mean >= MIN_INNER_V_MEAN
        and features.center_to_ring_v >= MIN_CENTER_TO_RING_V
        and features.glow_score >= MIN_GLOW_SCORE
        and radial_brightness_ratio >= MIN_RADIAL_BRIGHTNESS_RATIO
    )
    return (
        features.v_max >= 250.0
        and features.v_p95 >= 245.0
        and features.percent_hot_235 >= 0.06
        and features.percent_hot_245 >= 0.045
        and has_compact_emissive_core
    )


def _score(features, fill_ratio: float) -> float:
    return (
        min(1.0, features.v_p95 / 255.0) * 0.12
        + min(1.0, features.percent_hot_235 / 0.15) * 0.15
        + min(1.0, max(0.0, features.center_to_ring_v) / 55.0) * 0.25
        + min(1.0, features.glow_score / 125.0) * 0.22
        + min(1.0, features.inner_v_mean / 245.0) * 0.12
        + min(1.0, features.v_std / 35.0) * 0.06
        + min(1.0, features.s_mean / 70.0) * 0.03
        + min(1.0, fill_ratio / 0.55) * 0.05
    )


def _sort_by_rows(candidates: list[tuple[int, int, float]], radius: int):
    tolerance = max(10, int(round(radius * 1.35)))
    rows: list[list[tuple[int, int, float]]] = []

    for candidate in sorted(candidates, key=lambda item: item[1]):
        best_row = None
        best_distance = None
        for row in rows:
            average_y = sum(item[1] for item in row) / len(row)
            distance = abs(candidate[1] - average_y)
            if distance <= tolerance and (
                best_distance is None or distance < best_distance
            ):
                best_row = row
                best_distance = distance
        if best_row is None:
            rows.append([candidate])
        else:
            best_row.append(candidate)

    rows.sort(key=lambda row: sum(item[1] for item in row) / len(row))
    ordered = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda item: item[0]))
    return ordered


def detect_lit_leds(
    image,
    radius: int,
    max_leds: int = MAX_AUTOMATIC_LEDS,
    profile: str = "strict",
) -> AutomaticLedDetectionResult:
    started_at = time.perf_counter()
    if image is None or getattr(image, "size", 0) == 0:
        return AutomaticLedDetectionResult((), 0, 0.0, False)

    profile = "camera" if str(profile).lower() == "camera" else "strict"
    original_height, original_width = image.shape[:2]
    radius = max(3, int(radius))
    max_leds = max(1, min(MAX_AUTOMATIC_LEDS, int(max_leds)))
    scale = min(
        1.0,
        MAX_PROCESSING_DIMENSION / float(max(original_width, original_height)),
    )

    if scale < 1.0:
        work_image = cv2.resize(
            image,
            (
                int(round(original_width * scale)),
                int(round(original_height * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )
    else:
        work_image = image

    work_radius = max(3, int(round(radius * scale)))
    value = cv2.cvtColor(work_image, cv2.COLOR_BGR2HSV)[:, :, 2]
    value_blurred = cv2.GaussianBlur(value, (3, 3), 0)
    background = cv2.GaussianBlur(
        value_blurred,
        (0, 0),
        sigmaX=max(3.0, work_radius * 0.85),
    )
    contrast = cv2.subtract(value_blurred, background)

    if profile == "camera":
        candidate_mask = (
            ((value_blurred >= 180) & (contrast >= 10))
            | ((value_blurred >= 205) & (contrast >= 5))
        )
    else:
        candidate_mask = (
            ((value_blurred >= 220) & (contrast >= 12))
            | ((value_blurred >= 245) & (contrast >= 6))
        )

    mask = np.where(candidate_mask, 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask,
        connectivity=8,
    )
    minimum_area = max(3, int(math.pi * (work_radius * 0.12) ** 2))
    maximum_area = max(
        minimum_area + 1,
        int(math.pi * (work_radius * 2.2) ** 2),
    )
    candidates: list[tuple[int, int, float]] = []

    for component in range(1, count):
        width = int(stats[component, cv2.CC_STAT_WIDTH])
        height = int(stats[component, cv2.CC_STAT_HEIGHT])
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < minimum_area or area > maximum_area or width <= 0 or height <= 0:
            continue

        aspect_ratio = width / float(height)
        fill_ratio = area / float(width * height)
        if not 0.30 <= aspect_ratio <= 3.30 or fill_ratio < 0.12:
            continue

        work_x, work_y = centroids[component]
        center_x = int(round(work_x / scale))
        center_y = int(round(work_y / scale))
        if not validar_centro_led(
            center_x,
            center_y,
            radius,
            original_width,
            original_height,
        ):
            continue

        features = extrair_features_led(
            image,
            center_x,
            center_y,
            radius,
        )
        if not _matches_pattern(features, profile):
            continue

        candidate_score = _score(features, fill_ratio)
        minimum_score = 0.54 if profile == "camera" else 0.66
        if candidate_score >= minimum_score:
            candidates.append((center_x, center_y, candidate_score))

    selected: list[tuple[int, int, float]] = []
    minimum_distance = max(10.0, radius * 1.25)
    for candidate in sorted(candidates, key=lambda item: item[2], reverse=True):
        if any(
            math.hypot(candidate[0] - item[0], candidate[1] - item[1])
            < minimum_distance
            for item in selected
        ):
            continue
        selected.append(candidate)

    candidate_count = len(selected)
    truncated = candidate_count > max_leds
    selected = _sort_by_rows(selected[:max_leds], radius)
    leds = tuple(
        LedSelection(
            id=f"LED_{index:03d}",
            centro_x=center_x,
            centro_y=center_y,
            raio=radius,
        )
        for index, (center_x, center_y, _score_value) in enumerate(
            selected,
            start=1,
        )
    )
    return AutomaticLedDetectionResult(
        leds=leds,
        candidate_count=candidate_count,
        elapsed_seconds=time.perf_counter() - started_at,
        truncated=truncated,
    )
