from __future__ import annotations


def display_manual_transition_target_confirmed(analysis: dict) -> bool:
    """Libera a troca manual somente quando o próximo CHECK está completo.

    Durante BLUE→USB e USB→AUX, estados parciais podem coincidir com segmentos
    do modo anterior (principalmente enquanto o Bluetooth pisca). Esses estados
    nunca devem liberar o gate nem acumular NG. A transição só termina quando o
    analisador confirma integralmente o CHECK de destino.
    """
    return (
        isinstance(analysis, dict)
        and bool(analysis.get("ready"))
        and analysis.get("approved") is True
    )


def instalar_gate_estrito_transicao_manual_display_f3() -> None:
    """Substitui apenas o critério de entrada manual do auto-check Display F3."""
    from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin

    cls = DisplayAutomaticCheckF3Mixin
    if getattr(cls, "_odin_display_strict_manual_transition_gate", False):
        return

    cls._display_auto_has_manual_entry_evidence = staticmethod(
        display_manual_transition_target_confirmed
    )
    cls._odin_display_strict_manual_transition_gate = True


instalar_gate_estrito_transicao_manual_display_f3()
