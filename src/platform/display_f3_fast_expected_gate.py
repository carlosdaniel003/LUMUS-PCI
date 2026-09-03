from __future__ import annotations

from copy import deepcopy

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


F3_FAST_EXPECTED_GATE_SOURCE = "f3_expected_check_exact_template_fast_path"


def contexto_exige_captura_rapida_f3(context: dict | None) -> bool:
    """H1 e CHECKS transitórios não podem esperar debounce do estado físico.

    A liberação aqui não aprova o CHECK. Ela apenas deixa o analisador do CHECK
    atual olhar o frame imediatamente. A decisão continua sendo feita pelo
    gabarito exato das máscaras do próprio CHECK.
    """
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


def liberar_gate_fisico_para_check_rapido_f3(
    state: dict | None,
    context: dict | None,
) -> dict:
    """Permite análise imediata de H1/BLUE sem falsificar o estado físico.

    O estado detectado continua intacto para diagnóstico. Portanto, se a cena
    global disser USB enquanto o sequenciador aguarda BLUE, a interface ainda
    pode informar USB, mas o gate não impede o gabarito BLUE de examinar aquele
    frame. USB só será aceito como BLUE se todas as máscaras do gabarito BLUE
    realmente coincidirem, o que o analisador exato não permite por aproximação
    de estado físico.
    """
    result = deepcopy(state) if isinstance(state, dict) else {}
    if bool(result.get("allow_auto")):
        return result
    if not contexto_exige_captura_rapida_f3(context):
        return result

    result["allow_auto"] = True
    result["fast_expected_check_gate"] = True
    result["fast_expected_check_source"] = F3_FAST_EXPECTED_GATE_SOURCE
    return result


_INSTALLED = False


def instalar_gate_rapido_check_esperado_display_f3() -> None:
    """Instala a captura rápida depois do gabarito exato, somente no F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_physical_builder = physical_policy_module._build_physical_operational_state
    original_operational_builder = operational_module._build_operational_state

    def physical_builder(self, frame, project_name: str, context: dict | None):
        state = original_physical_builder(self, frame, project_name, context)
        return liberar_gate_fisico_para_check_rapido_f3(state, context)

    physical_policy_module._build_physical_operational_state = physical_builder

    if original_operational_builder is original_physical_builder:
        operational_module._build_operational_state = physical_builder
    else:
        def operational_builder(self, frame, project_name: str, context: dict | None):
            state = original_operational_builder(self, frame, project_name, context)
            return liberar_gate_fisico_para_check_rapido_f3(state, context)

        operational_module._build_operational_state = operational_builder

    DisplayAutomaticCheckF3Mixin._display_f3_fast_expected_gate_installed = True
    _INSTALLED = True
