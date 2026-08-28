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
F2_BOARD_STATUS_ANALYZED_OK = "analyzed_ok"
F2_BOARD_STATUS_ANALYZED_NG = "analyzed_ng"


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


def status_resultado_placa_analisada_f2(resultado: str | None) -> str | None:
    normalized = str(resultado or "").strip().upper()
    if normalized == "OK":
        return F2_BOARD_STATUS_ANALYZED_OK
    if normalized == "NG":
        return F2_BOARD_STATUS_ANALYZED_NG
    return None


class F2BoardStatusDisplayMixin:
    """Publica na tela F2 o estado físico atual da placa no modo automático."""

    def _f2_auto_publish_states(
        self,
        states: dict[str, str],
        presence: str = F2_BOARD_PRESENCE_UNAVAILABLE,
    ) -> None:
        result = super()._f2_auto_publish_states(states, presence)

        status = status_visual_placa_f2(presence, states)
        same_board_locked = (
            bool(getattr(self, "_f2_auto_cycle_locked", False))
            and not bool(getattr(self, "_f2_auto_waiting_new_board_off", False))
            and str(presence or "").strip().lower() != F2_BOARD_PRESENCE_EMPTY
        )
        if same_board_locked:
            analyzed_status = status_resultado_placa_analisada_f2(
                getattr(self, "_f2_auto_last_inspection_result", None)
            )
            if analyzed_status is not None:
                status = analyzed_status

        window = getattr(self, "operacao_window", None)
        setter = getattr(window, "set_board_presence_status", None)
        if callable(setter):
            setter(
                status,
                enabled=bool(self._f2_auto_enabled()),
            )
        return result
