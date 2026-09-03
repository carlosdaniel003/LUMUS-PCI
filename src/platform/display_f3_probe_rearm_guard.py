from __future__ import annotations

import src.platform.display_f3_live_diagnostic_trace as trace_module


F3_PROBE_REARM_BLOCK_REASON = "aguardando_rearme_fisico"


def rearme_fisico_ativo_display_f3(app) -> bool:
    """Retorna True enquanto a placa anterior ainda não liberou um novo ciclo.

    A máquina de sequência volta internamente ao primeiro CHECK quando registra
    OK/NG terminal. Isso não significa que uma nova placa já pode ser analisada:
    o F3 precisa primeiro confirmar suporte vazio e, depois, presença de uma nova
    placa. A sonda positiva não pode furar esse handoff físico.
    """
    return bool(
        getattr(app, "_display_f3_waiting_empty_rearm", False)
        or getattr(app, "_display_f3_waiting_new_board_after_empty", False)
    )


def avancar_sonda_com_guard_rearme_display_f3(
    app,
    context_before: dict | None,
    analysis: dict | None,
    stability: dict,
    original_advance,
) -> dict | None:
    """Impede qualquer avanço da sonda enquanto o rearme físico estiver ativo."""
    if not rearme_fisico_ativo_display_f3(app):
        return original_advance(app, context_before, analysis, stability)

    # Apaga qualquer confirmação acumulada da placa anterior. Assim nem um H1
    # ainda visível após o último CHECK, nem uma fotografia coincidente durante a
    # retirada da placa, pode ser reutilizado como início da placa seguinte.
    app._display_f3_live_probe_ok_frames = 0
    app._display_f3_live_probe_signature = None

    if isinstance(analysis, dict):
        analysis["positive_probe_blocked"] = True
        analysis["positive_probe_blocked_reason"] = F3_PROBE_REARM_BLOCK_REASON

    return {
        "advanced": False,
        "reason": F3_PROBE_REARM_BLOCK_REASON,
        "waiting_empty_rearm": bool(
            getattr(app, "_display_f3_waiting_empty_rearm", False)
        ),
        "waiting_new_board_after_empty": bool(
            getattr(app, "_display_f3_waiting_new_board_after_empty", False)
        ),
    }


_INSTALLED = False


def instalar_guard_sonda_rearme_display_f3() -> None:
    """Fecha o atalho da sonda positiva sem alterar nenhum fluxo da Produção F2."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_advance = trace_module._advance_positive_probe_if_needed

    def guarded_advance(app, context_before, analysis, stability):
        return avancar_sonda_com_guard_rearme_display_f3(
            app,
            context_before,
            analysis,
            stability,
            original_advance,
        )

    trace_module._advance_positive_probe_if_needed = guarded_advance
    trace_module._display_f3_probe_rearm_guard_installed = True
    _INSTALLED = True
