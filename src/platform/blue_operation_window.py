from __future__ import annotations

from src.platform.raspberry_runtime_fixes import (
    StableRaspberryOperationWindow,
)


def substituir_texto_marcacao_azul(texto: str) -> str:
    return str(texto).replace(
        "Marcados em vermelho na câmera",
        "Marcados em azul na câmera",
    )


class BlueRaspberryOperationWindow(StableRaspberryOperationWindow):
    """Tela F2 com todas as referências visuais de NG em azul."""

    PREVIEW_FAILED = "#2563EB"

    def show_result(
        self,
        is_ok: bool,
        elapsed_seconds: float,
        failed_led_ids: tuple[str, ...],
        total: int,
        ok_count: int,
        ng_count: int,
    ) -> None:
        super().show_result(
            is_ok=is_ok,
            elapsed_seconds=elapsed_seconds,
            failed_led_ids=failed_led_ids,
            total=total,
            ok_count=ok_count,
            ng_count=ng_count,
        )

        if not is_ok:
            texto = str(self.detail_label.cget("text"))
            self.detail_label.configure(
                text=substituir_texto_marcacao_azul(texto)
            )
