from __future__ import annotations

from dataclasses import dataclass
import atexit
import os
import re
import shutil
import signal
import subprocess
import sys
from typing import Callable


@dataclass(frozen=True)
class XSetDisplayState:
    screensaver_timeout: int | None = None
    screensaver_cycle: int | None = None
    dpms_enabled: bool | None = None
    dpms_standby: int | None = None
    dpms_suspend: int | None = None
    dpms_off: int | None = None


def parse_xset_display_state(output: str) -> XSetDisplayState:
    text = str(output or "")
    screensaver = re.search(
        r"timeout:\s*(\d+)\s+cycle:\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    dpms_enabled_match = re.search(
        r"DPMS\s+is\s+(Enabled|Disabled)",
        text,
        flags=re.IGNORECASE,
    )
    dpms_times = re.search(
        r"Standby:\s*(\d+)\s+Suspend:\s*(\d+)\s+Off:\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )

    return XSetDisplayState(
        screensaver_timeout=(
            int(screensaver.group(1)) if screensaver else None
        ),
        screensaver_cycle=(
            int(screensaver.group(2)) if screensaver else None
        ),
        dpms_enabled=(
            dpms_enabled_match.group(1).lower() == "enabled"
            if dpms_enabled_match
            else None
        ),
        dpms_standby=(
            int(dpms_times.group(1)) if dpms_times else None
        ),
        dpms_suspend=(
            int(dpms_times.group(2)) if dpms_times else None
        ),
        dpms_off=(
            int(dpms_times.group(3)) if dpms_times else None
        ),
    )


class LinuxDisplayAwakeController:
    """Impede bloqueio, screensaver e DPMS somente enquanto o ODIN está aberto."""

    COMMAND_TIMEOUT_S = 0.8

    def __init__(
        self,
        root,
        platform_name: str | None = None,
        environ: dict | None = None,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        self.root = root
        self.platform_name = str(platform_name or sys.platform)
        self.environ = dict(os.environ if environ is None else environ)
        self._which = which
        self._runner = runner
        self._popen = popen

        self._active = False
        self._window_id: int | None = None
        self._xdg_suspended = False
        self._xset_state: XSetDisplayState | None = None
        self._processes: list = []
        self._strategies: list[str] = []

    @property
    def active(self) -> bool:
        return bool(self._active)

    @property
    def strategies(self) -> tuple[str, ...]:
        return tuple(self._strategies)

    def _command_available(self, command: str) -> bool:
        try:
            return bool(self._which(command))
        except Exception:
            return False

    def _run(self, command: list[str]):
        try:
            return self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.COMMAND_TIMEOUT_S,
                check=False,
                env=self.environ,
            )
        except Exception:
            return None

    def _spawn(self, command: list[str]):
        try:
            process = self._popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=self.environ,
            )
        except Exception:
            return None
        self._processes.append(process)
        return process

    def _has_graphical_session(self) -> bool:
        return bool(
            self.environ.get("DISPLAY")
            or self.environ.get("WAYLAND_DISPLAY")
        )

    def _suspend_xdg_screensaver(self) -> None:
        if not self._command_available("xdg-screensaver"):
            return
        try:
            self.root.update_idletasks()
            self._window_id = int(self.root.winfo_id())
        except Exception:
            self._window_id = None
        if self._window_id is None:
            return

        result = self._run(
            ["xdg-screensaver", "suspend", str(self._window_id)]
        )
        if result is not None and int(result.returncode) == 0:
            self._xdg_suspended = True
            self._strategies.append("xdg-screensaver")

    def _disable_x11_blanking(self) -> None:
        if not self.environ.get("DISPLAY"):
            return
        if not self._command_available("xset"):
            return

        query = self._run(["xset", "q"])
        if query is not None and int(query.returncode) == 0:
            self._xset_state = parse_xset_display_state(query.stdout)

        result_saver = self._run(["xset", "s", "off"])
        result_dpms = self._run(["xset", "-dpms"])
        if any(
            result is not None and int(result.returncode) == 0
            for result in (result_saver, result_dpms)
        ):
            self._strategies.append("xset")

    def _start_session_inhibitors(self) -> None:
        commands = (
            (
                "gnome-session-inhibit",
                [
                    "gnome-session-inhibit",
                    "--inhibit",
                    "idle:suspend",
                    "--reason",
                    "ODIN em operação",
                    "--inhibit-only",
                ],
            ),
            (
                "systemd-inhibit",
                [
                    "systemd-inhibit",
                    "--what=idle:sleep",
                    "--who=ODIN",
                    "--why=ODIN em operação",
                    "--mode=block",
                    "sleep",
                    "infinity",
                ],
            ),
        )

        for executable, command in commands:
            if not self._command_available(executable):
                continue
            if self._spawn(command) is not None:
                self._strategies.append(executable)

    def start(self) -> None:
        if self._active or not self.platform_name.startswith("linux"):
            return
        if not self._has_graphical_session():
            return

        self._active = True
        self._strategies = []
        self._suspend_xdg_screensaver()
        self._disable_x11_blanking()
        self._start_session_inhibitors()

    def _restore_xset_state(self) -> None:
        state = self._xset_state
        if state is None or not self._command_available("xset"):
            return

        if state.screensaver_timeout is not None:
            if state.screensaver_timeout <= 0:
                self._run(["xset", "s", "off"])
            else:
                command = [
                    "xset",
                    "s",
                    str(state.screensaver_timeout),
                ]
                if state.screensaver_cycle is not None:
                    command.append(str(state.screensaver_cycle))
                self._run(command)

        if state.dpms_enabled is True:
            self._run(["xset", "+dpms"])
            if None not in (
                state.dpms_standby,
                state.dpms_suspend,
                state.dpms_off,
            ):
                self._run(
                    [
                        "xset",
                        "dpms",
                        str(state.dpms_standby),
                        str(state.dpms_suspend),
                        str(state.dpms_off),
                    ]
                )
        elif state.dpms_enabled is False:
            self._run(["xset", "-dpms"])

    @staticmethod
    def _stop_process(process) -> None:
        try:
            if process.poll() is not None:
                return
        except Exception:
            return

        try:
            pid = int(process.pid)
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                process.terminate()
            except Exception:
                return

        try:
            process.wait(timeout=0.4)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False

        if self._xdg_suspended and self._window_id is not None:
            self._run(
                ["xdg-screensaver", "resume", str(self._window_id)]
            )
        self._xdg_suspended = False

        self._restore_xset_state()
        self._xset_state = None

        for process in reversed(self._processes):
            self._stop_process(process)
        self._processes.clear()


class LinuxDisplayAwakeMixin:
    """Ativa a inibição de tela após o Tk mapear a janela principal."""

    DISPLAY_AWAKE_START_DELAY_MS = 350

    def __init__(self, root, *args, **kwargs) -> None:
        self._display_awake_controller = None
        self._display_awake_after_id = None
        super().__init__(root, *args, **kwargs)

        self._display_awake_controller = LinuxDisplayAwakeController(root)
        try:
            root.bind(
                "<Destroy>",
                self._on_display_awake_destroy,
                add="+",
            )
        except Exception:
            pass

        try:
            self._display_awake_after_id = root.after(
                self.DISPLAY_AWAKE_START_DELAY_MS,
                self._start_display_awake,
            )
        except Exception:
            self._start_display_awake()

        atexit.register(self._stop_display_awake)

    def _start_display_awake(self) -> None:
        self._display_awake_after_id = None
        controller = self._display_awake_controller
        if controller is not None:
            controller.start()

    def _stop_display_awake(self) -> None:
        after_id = self._display_awake_after_id
        self._display_awake_after_id = None
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass

        controller = self._display_awake_controller
        if controller is not None:
            controller.stop()

    def _on_display_awake_destroy(self, event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not self.root:
            return
        self._stop_display_awake()
