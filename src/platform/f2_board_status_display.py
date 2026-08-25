from __future__ import annotations

from src.core.segment_low_light import STATUS_ACESO
from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_PRESENT,
    F2_BOARD_PRESENCE_UNAVAILABLE,
)


F2_BOARD_STATUS_ON = "board_on"
F2_BOARD_STATUS_OFF = "board_off"
F2_BOARD_STATUS_EMPTY = "empty_support"
F2_BOARD_STATUS_UNKNOWN = "unknown"
F2_BOARD_STATUS_UNAVAILABLE = "unavailable"


def status_visual_placa_f2(
    presence: str,
    states: dict[str, str] | None,
) -> str:
    """Traduz presença + estados dos LEDs para o status operacional do F2.

    A presença estrutural continua vindo das três referências completas do projeto.
    Quando a placa está presente, o estado LIGADA/DESLIGADA usa o diagnóstico vivo
    dos LEDs: qualquer ACESO/POUCA_LUZ significa que a placa está energizada.
    """
    normalized_presence = str(presence or "").strip().lower()
    if normalized_presence == F2_BOARD_PRESENCE_EMPTY:
        return F2_BOARD_STATUS_EMPTY
    if normalized_presence == F2_BOARD_PRESENCE_UNAVAILABLE:
        return F2_BOARD_STATUS_UNAVAILABLE
    if normalized_presence != F2_BOARD_PRESENCE_PRESENT:
        return F2_BOARD_STATUS_UNKNOWN

    has_light = any(
        str(status or "").strip().upper()
        in {STATUS_ACESO, "POUCA_LUZ", "POUCA LUZ"}
        for status in dict(states or {}).values()
    )
    return F2_BOARD_STATUS_ON if has_light else F2_BOARD_STATUS_OFF


class F2BoardStatusDisplayMixin:
    """Publica na tela F2 o estado físico atual da placa no modo automático."""

    def _f2_auto_publish_states(
        self,
        states: dict[str, str],
        presence: str = F2_BOARD_PRESENCE_UNAVAILABLE,
    ) -> None:
        result = super()._f2_auto_publish_states(states, presence)

        window = getattr(self, "operacao_window", None)
        setter = getattr(window, "set_board_presence_status", None)
        if callable(setter):
            setter(
                status_visual_placa_f2(presence, states),
                enabled=bool(self._f2_auto_enabled()),
            )
        return result
