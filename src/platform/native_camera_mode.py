from __future__ import annotations

from dataclasses import dataclass
import platform
import re
import shutil
import subprocess
from typing import Callable


@dataclass(frozen=True)
class NativeCameraMode:
    width: int
    height: int
    fps: float
    format: str

    @property
    def pixels(self) -> int:
        return int(self.width) * int(self.height)


def parse_v4l2_formats_ext(output: str) -> tuple[NativeCameraMode, ...]:
    modes: list[NativeCameraMode] = []
    current_format = ""
    current_size: tuple[int, int] | None = None
    current_fps: list[float] = []

    def flush() -> None:
        nonlocal current_size, current_fps
        if current_size is None or not current_format:
            current_size = None
            current_fps = []
            return
        fps = max(current_fps) if current_fps else 0.0
        modes.append(
            NativeCameraMode(
                width=int(current_size[0]),
                height=int(current_size[1]),
                fps=float(fps),
                format=str(current_format).upper(),
            )
        )
        current_size = None
        current_fps = []

    for raw_line in str(output).splitlines():
        line = raw_line.strip()
        format_match = re.search(r"\[\d+\]:\s*'([^']+)'", line)
        if format_match:
            flush()
            current_format = format_match.group(1).upper()
            continue

        size_match = re.search(
            r"Size:\s*Discrete\s*(\d+)x(\d+)",
            line,
            flags=re.IGNORECASE,
        )
        if size_match:
            flush()
            current_size = (
                int(size_match.group(1)),
                int(size_match.group(2)),
            )
            continue

        fps_match = re.search(
            r"\(([0-9]+(?:\.[0-9]+)?)\s*fps\)",
            line,
            flags=re.IGNORECASE,
        )
        if fps_match and current_size is not None:
            current_fps.append(float(fps_match.group(1)))

    flush()

    unique: dict[tuple[int, int, str], NativeCameraMode] = {}
    for mode in modes:
        key = (mode.width, mode.height, mode.format)
        previous = unique.get(key)
        if previous is None or mode.fps > previous.fps:
            unique[key] = mode
    return tuple(unique.values())


def raspberry_safe_resolution_limit() -> tuple[int, int] | None:
    machine = platform.machine().lower()
    if machine.startswith(("arm", "aarch64")):
        return 1920, 1080
    return None


def select_native_camera_mode(
    modes: tuple[NativeCameraMode, ...],
    target_fps: float = 30.0,
    max_resolution: tuple[int, int] | None = None,
) -> NativeCameraMode | None:
    if not modes:
        return None

    filtered = list(modes)
    if max_resolution is not None:
        max_width, max_height = max_resolution
        within_limit = [
            mode
            for mode in filtered
            if mode.width <= int(max_width)
            and mode.height <= int(max_height)
        ]
        if within_limit:
            filtered = within_limit

    target_fps = max(1.0, float(target_fps))

    def score(mode: NativeCameraMode) -> tuple[int, int, int, float]:
        normalized_format = mode.format.upper()
        compressed = int(normalized_format in ("MJPG", "JPEG"))
        supports_target = int(mode.fps >= target_fps - 0.5)
        return (
            supports_target,
            compressed,
            mode.pixels,
            float(mode.fps),
        )

    return max(filtered, key=score)


def get_native_camera_mode(
    device: str,
    target_fps: float = 30.0,
    max_resolution: tuple[int, int] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> NativeCameraMode | None:
    if not shutil.which("v4l2-ctl"):
        return None

    try:
        process = runner(
            ["v4l2-ctl", "-d", str(device), "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except Exception:
        return None

    if int(process.returncode) != 0:
        return None

    modes = parse_v4l2_formats_ext(process.stdout)
    return select_native_camera_mode(
        modes=modes,
        target_fps=target_fps,
        max_resolution=max_resolution,
    )
