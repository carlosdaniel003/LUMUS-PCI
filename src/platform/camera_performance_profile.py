from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median, pstdev


@dataclass(frozen=True)
class CameraPerformanceResult:
    candidate_key: str
    width: int
    height: int
    measured_fps: float
    valid_ratio: float
    corrupted_ratio: float
    flicker_ratio: float
    jitter_ratio: float
    valid_frames: int
    total_reads: int
    comfortable: bool
    excellent: bool
    score: float
    reason: str = ""

    @property
    def pixels(self) -> int:
        return max(0, int(self.width)) * max(0, int(self.height))


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, fraction))))
    return ordered[index]


def calculate_camera_performance(
    candidate_key: str,
    width: int,
    height: int,
    timestamps: list[float],
    valid_flags: list[bool],
    corrupted_flags: list[bool],
    brightness_values: list[float],
    target_fps: float = 30.0,
    target_resolution: tuple[int, int] = (1920, 1080),
    reason: str = "",
) -> CameraPerformanceResult:
    total_reads = len(valid_flags)
    valid_frames = sum(bool(value) for value in valid_flags)
    valid_ratio = valid_frames / max(1, total_reads)

    corrupted_count = sum(bool(value) for value in corrupted_flags)
    corrupted_ratio = corrupted_count / max(1, valid_frames)

    measured_fps = 0.0
    intervals: list[float] = []
    if len(timestamps) >= 2:
        duration = float(timestamps[-1]) - float(timestamps[0])
        if duration > 0:
            measured_fps = (len(timestamps) - 1) / duration
        intervals = [
            float(current) - float(previous)
            for previous, current in zip(timestamps, timestamps[1:])
            if float(current) > float(previous)
        ]

    jitter_ratio = 1.0
    if intervals:
        average_interval = sum(intervals) / len(intervals)
        jitter_ratio = (
            pstdev(intervals) / average_interval
            if len(intervals) >= 2 and average_interval > 0
            else 0.0
        )

    brightness_deltas = [
        abs(float(current) - float(previous))
        for previous, current in zip(
            brightness_values,
            brightness_values[1:],
        )
    ]
    reference_brightness = max(
        12.0,
        median(brightness_values) if brightness_values else 12.0,
    )
    flicker_ratio = (
        _percentile(brightness_deltas, 0.90) / reference_brightness
        if brightness_deltas
        else 0.0
    )

    target_fps = max(1.0, float(target_fps))
    fps_ratio = measured_fps / target_fps
    comfortable = bool(
        total_reads >= 6
        and valid_ratio >= 0.95
        and corrupted_ratio <= 0.02
        and fps_ratio >= 0.80
        and jitter_ratio <= 0.40
        and flicker_ratio <= 0.18
    )
    excellent = bool(
        total_reads >= 8
        and valid_ratio >= 0.98
        and corrupted_ratio == 0.0
        and fps_ratio >= 0.90
        and jitter_ratio <= 0.25
        and flicker_ratio <= 0.10
    )

    target_pixels = max(1, int(target_resolution[0]) * int(target_resolution[1]))
    pixels = max(1, int(width) * int(height))
    resolution_ratio = pixels / target_pixels
    resolution_delta = math.log2(resolution_ratio)
    if resolution_ratio >= 1.0:
        resolution_score = min(18.0, resolution_delta * 8.0)
    else:
        resolution_score = max(-28.0, resolution_delta * 15.0)

    score = (
        valid_ratio * 45.0
        + min(1.0, max(0.0, fps_ratio)) * 32.0
        + max(0.0, 1.0 - min(1.0, jitter_ratio)) * 10.0
        + max(0.0, 1.0 - min(1.0, flicker_ratio)) * 8.0
        + max(0.0, 1.0 - min(1.0, corrupted_ratio * 10.0)) * 20.0
        + resolution_score
    )
    if (int(width), int(height)) == tuple(target_resolution):
        score += 10.0
    if excellent and resolution_ratio > 1.0:
        score += 12.0
    if not comfortable:
        score -= 65.0

    return CameraPerformanceResult(
        candidate_key=str(candidate_key),
        width=max(0, int(width)),
        height=max(0, int(height)),
        measured_fps=round(float(measured_fps), 2),
        valid_ratio=round(float(valid_ratio), 4),
        corrupted_ratio=round(float(corrupted_ratio), 4),
        flicker_ratio=round(float(flicker_ratio), 4),
        jitter_ratio=round(float(jitter_ratio), 4),
        valid_frames=int(valid_frames),
        total_reads=int(total_reads),
        comfortable=comfortable,
        excellent=excellent,
        score=round(float(score), 3),
        reason=str(reason),
    )


def select_best_camera_performance(
    results: tuple[CameraPerformanceResult, ...],
    target_resolution: tuple[int, int] = (1920, 1080),
) -> CameraPerformanceResult | None:
    if not results:
        return None

    target_pixels = max(1, int(target_resolution[0]) * int(target_resolution[1]))
    excellent_high = [
        result
        for result in results
        if result.excellent and result.pixels >= target_pixels
    ]
    if excellent_high:
        return max(
            excellent_high,
            key=lambda result: (result.pixels, result.score),
        )

    target_comfortable = [
        result
        for result in results
        if result.comfortable
        and (result.width, result.height) == tuple(target_resolution)
    ]
    if target_comfortable:
        return max(target_comfortable, key=lambda result: result.score)

    comfortable = [result for result in results if result.comfortable]
    if comfortable:
        return max(
            comfortable,
            key=lambda result: (
                result.score,
                -abs(result.pixels - target_pixels),
            ),
        )

    return max(results, key=lambda result: result.score)
