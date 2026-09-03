from __future__ import annotations

import src.platform.display_f3_live_diagnostic_trace as trace_module


def frames_necessarios_sonda_positiva_f3(app, context: dict | None) -> int:
    """H1 e BLUE são capturados no primeiro frame que bate 100% com o gabarito.

    Esta regra vale apenas para a sonda positiva do gabarito exato. Ela nunca
    gera NG e nunca libera uma classificação parcial: o analyzer precisa aprovar
    todas as máscaras ativas do CHECK. Demais CHECKS estáveis mantêm 2 frames.
    """
    if not isinstance(context, dict):
        return 2

    try:
        if app._display_auto_is_reference_gate(context):
            return 1
    except Exception:
        pass

    try:
        if app._display_auto_is_transient_check(context):
            return 1
    except Exception:
        pass

    return 2


_INSTALLED = False


def instalar_captura_h1_um_frame_display_f3() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    trace_module._probe_required_frames = frames_necessarios_sonda_positiva_f3
    _INSTALLED = True
