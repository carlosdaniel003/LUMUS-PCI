from __future__ import annotations

from copy import deepcopy

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


F3_FAST_EXPECTED_GATE_SOURCE = "f3_expected_check_exact_template_fast_path"
F3_FAST_EXPECTED_BLOCKING_KINDS = frozenset({"off", "empty", "unavailable"})


def contexto_exige_captura_rapida_f3(context: dict | None) -> bool:
    """H1 e CHECKS transitórios podem usar o caminho rápido do F3."""
    if not isinstance(context, dict):
        return False

    try:
        if DisplayAutomaticCheckF3Mixin._display_auto_is_reference_gate(context):
            return True
    except Exception:
        pass

    try:
        return bool(
            DisplayAutomaticCheckF3Mixin._display_auto_is_transient_check(context)
        )
    except Exception:
        return False


def _estado_tem_evidencia_fisica_ligada_f3(state: dict | None) -> bool:
    """Fast path só existe depois de alguma evidência positiva de display ligado.

    OFF, suporte vazio e indisponível são autoridades absolutas. Um estado
    UNKNOWN também não libera análise por si só: ele só pode liberar quando o
    UNKNOWN existe exclusivamente por debounce de uma transição cujo candidato
    físico bruto já é algum CHECK ligado (``check:<id>``).
    """
    if not isinstance(state, dict):
        return False

    kind = str(state.get("kind") or "unknown").strip().lower()
    if kind in F3_FAST_EXPECTED_BLOCKING_KINDS:
        return False
    if kind == "check":
        return True
    if kind != "unknown":
        return False

    if not bool(state.get("physical_transition_pending")):
        return False

    pending_key = str(state.get("pending_physical_state_key") or "").strip()
    return bool(pending_key.startswith("check:"))


def liberar_gate_fisico_para_check_rapido_f3(
    state: dict | None,
    context: dict | None,
) -> dict:
    """Acelera H1/BLUE sem jamais transformar placa apagada em display ligado.

    O fast path não aprova nenhum CHECK. Ele apenas permite que o gabarito exato
    do CHECK esperado examine imediatamente um frame quando já existe evidência
    física de que algum estado ligado está presente. Isso preserva a captura de
    BLUE transitório, mas torna OFF/EMPTY estados invioláveis.
    """
    result = deepcopy(state) if isinstance(state, dict) else {}
    if bool(result.get("allow_auto")):
        return result
    if not contexto_exige_captura_rapida_f3(context):
        return result
    if not _estado_tem_evidencia_fisica_ligada_f3(result):
        return result

    result["allow_auto"] = True
    result["fast_expected_check_gate"] = True
    result["fast_expected_check_source"] = F3_FAST_EXPECTED_GATE_SOURCE
    return result


def _anexar_candidato_fisico_pendente_f3(self, state: dict | None) -> dict:
    """Expõe ao fast path qual candidato bruto está aguardando debounce."""
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "").strip().lower() != "unknown":
        return result
    if not bool(result.get("physical_transition_pending")):
        return result

    pending_key = str(
        getattr(self, "_display_f3_physical_pending_key", "") or ""
    ).strip()
    if pending_key:
        result["pending_physical_state_key"] = pending_key
    return result


_INSTALLED = False


def instalar_gate_rapido_check_esperado_display_f3() -> None:
    """Instala captura rápida e as últimas políticas exclusivas do F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_physical_builder = physical_policy_module._build_physical_operational_state
    original_operational_builder = operational_module._build_operational_state

    def physical_builder(self, frame, project_name: str, context: dict | None):
        state = original_physical_builder(self, frame, project_name, context)
        state = _anexar_candidato_fisico_pendente_f3(self, state)
        return liberar_gate_fisico_para_check_rapido_f3(state, context)

    physical_policy_module._build_physical_operational_state = physical_builder

    if original_operational_builder is original_physical_builder:
        operational_module._build_operational_state = physical_builder
    else:
        def operational_builder(self, frame, project_name: str, context: dict | None):
            state = original_operational_builder(self, frame, project_name, context)
            state = _anexar_candidato_fisico_pendente_f3(self, state)
            return liberar_gate_fisico_para_check_rapido_f3(state, context)

        operational_module._build_operational_state = operational_builder

    DisplayAutomaticCheckF3Mixin._display_f3_fast_expected_gate_installed = True

    # Uma única camada é responsável pelo workspace. A antiga extensão
    # display_f3_responsive_config não é mais instalada porque disputava geometria
    # e maximização com o workspace final.
    from src.platform.display_f3_workspace_ui import (
        instalar_workspace_telas_display_f3,
    )

    instalar_workspace_telas_display_f3()

    from src.platform.display_f3_unknown_debug_fix import (
        instalar_correcao_unknown_e_debug_display_f3,
    )

    instalar_correcao_unknown_e_debug_display_f3()

    from src.platform.display_f3_live_diagnostic_trace import (
        instalar_rastreio_ao_vivo_debug_display_f3,
    )

    instalar_rastreio_ao_vivo_debug_display_f3()

    from src.platform.display_f3_debug_toggle import (
        instalar_toggle_debug_tecnico_display_f3,
    )

    instalar_toggle_debug_tecnico_display_f3()

    from src.platform.display_f3_h1_single_frame_probe import (
        instalar_captura_h1_um_frame_display_f3,
    )

    instalar_captura_h1_um_frame_display_f3()

    from src.platform.display_f3_probe_rearm_guard import (
        instalar_guard_sonda_rearme_display_f3,
    )

    instalar_guard_sonda_rearme_display_f3()

    from src.platform.display_f3_runtime_performance_guard import (
        instalar_guard_performance_runtime_display_f3,
    )

    instalar_guard_performance_runtime_display_f3()

    from src.platform.display_f3_zero_cost_debug_runtime import (
        instalar_runtime_debug_off_custo_zero_display_f3,
    )

    instalar_runtime_debug_off_custo_zero_display_f3()

    from src.platform.display_f3_reference_preview_rotation import (
        instalar_rotacao_preview_referencias_display_f3,
    )

    instalar_rotacao_preview_referencias_display_f3()

    # Performance deve ficar por fora dos wrappers históricos.
    from src.platform.display_f3_final_performance import (
        instalar_performance_final_display_f3,
    )

    instalar_performance_final_display_f3()

    # Contrato operacional é a última camada de todas: otimização nenhuma pode
    # voltar a desativar máscaras ou alterar a assinatura do Configurar.
    from src.platform.display_f3_runtime_contract_fix import (
        instalar_contrato_runtime_display_f3,
    )

    instalar_contrato_runtime_display_f3()
    _INSTALLED = True
