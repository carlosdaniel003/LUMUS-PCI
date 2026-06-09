import ctypes
from ctypes import wintypes


def formatar_geometria_janela(largura_janela: int, altura_janela: int, posicao_x: int, posicao_y: int) -> str:
    sinal_x = "+" if posicao_x >= 0 else "-"
    sinal_y = "+" if posicao_y >= 0 else "-"

    return (
        f"{int(largura_janela)}x{int(altura_janela)}"
        f"{sinal_x}{abs(int(posicao_x))}"
        f"{sinal_y}{abs(int(posicao_y))}"
    )


def obter_geometria_monitor_atual(self) -> dict:
    self.root.update_idletasks()

    try:
        monitor_default_to_nearest = 2

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        hwnd = wintypes.HWND(int(self.root.winfo_id()))
        monitor = ctypes.windll.user32.MonitorFromWindow(hwnd, monitor_default_to_nearest)

        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)

        sucesso = ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info))

        if not sucesso:
            raise RuntimeError("GetMonitorInfoW falhou.")

        monitor_x = int(monitor_info.rcMonitor.left)
        monitor_y = int(monitor_info.rcMonitor.top)
        monitor_largura = int(monitor_info.rcMonitor.right - monitor_info.rcMonitor.left)
        monitor_altura = int(monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top)

        work_x = int(monitor_info.rcWork.left)
        work_y = int(monitor_info.rcWork.top)
        work_largura = int(monitor_info.rcWork.right - monitor_info.rcWork.left)
        work_altura = int(monitor_info.rcWork.bottom - monitor_info.rcWork.top)

        return {
            "monitor_x": monitor_x,
            "monitor_y": monitor_y,
            "monitor_largura": monitor_largura,
            "monitor_altura": monitor_altura,
            "work_x": work_x,
            "work_y": work_y,
            "work_largura": work_largura,
            "work_altura": work_altura,
        }

    except Exception:
        largura_tela = self.root.winfo_screenwidth()
        altura_tela = self.root.winfo_screenheight()

        return {
            "monitor_x": 0,
            "monitor_y": 0,
            "monitor_largura": largura_tela,
            "monitor_altura": altura_tela,
            "work_x": 0,
            "work_y": 0,
            "work_largura": largura_tela,
            "work_altura": altura_tela,
        }