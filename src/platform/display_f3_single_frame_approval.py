from __future__ import annotations

"""Contrato final de aprovação em um único frame para o Display F3.

A regra é genérica e vale para qualquer CHECK atual ou futuro. Ela reduz somente
os frames positivos necessários para registrar OK. O debounce de NG permanece
conservador e os gates físicos/semânticos continuam obrigatórios.
"""

import src.platform.display_f3_h1_single_frame_probe as probe_module
import src.platform.display_f3_live_diagnostic_trace as trace_module
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


F3_OK_REQUIRED_FRAMES = 1


def frames_necessarios_aprovacao_f3(_app=None, _context: dict | None = None) -> int:
    """Todo CHECK aprovado precisa de exatamente um frame positivo válido."""
    return F3_OK_REQUIRED_FRAMES


_INSTALLED = False


def instalar_aprovacao_um_frame_display_f3() -> None:
    """Aplica a regra a runtime produtivo, sonda exata e estabilidade final."""
    global _INSTALLED
    if _INSTALLED:
        return

    # Runtime produtivo e display_f3_final_check_stability consultam este valor
    # dinamicamente, portanto a regra também cobre CHECKS criados futuramente.
    DisplayAutomaticCheckF3Mixin.DISPLAY_AUTO_OK_STABLE_FRAMES = F3_OK_REQUIRED_FRAMES

    # A sonda positiva possui um debounce próprio. Substituímos a autoridade
    # genérica e a referência já capturada pelo rastreador para manter um único
    # contrato de aprovação em todo o F3.
    probe_module.frames_necessarios_sonda_positiva_f3 = frames_necessarios_aprovacao_f3
    trace_module._probe_required_frames = frames_necessarios_aprovacao_f3

    DisplayAutomaticCheckF3Mixin._display_f3_single_frame_approval_installed = True
    _INSTALLED = True
