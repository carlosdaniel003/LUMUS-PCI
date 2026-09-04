from __future__ import annotations

"""Quebra o deadlock OFF -> analisador bloqueado do Display F3.

A comparação global pode chamar um H1 real de PLACA DESLIGADA porque a maior
parte da cena não muda. O gate anterior tentava corrigir isso usando a última
análise de máscaras, mas quando o estado físico era OFF essa análise não chegava
a executar. Esta camada usa a evidência CHECK x PLACA DESLIGADA já existente e
calculada diretamente no frame atual para responder apenas se há energia.

Ela nunca aprova H1/BLUE/USB/AUX. Quando a energia é inequívoca, apenas troca o
estado físico de falso OFF para PLACA LIGADA e libera o analisador oficial.
"""

import time
from copy import deepcopy

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
import src.platform.display_f3_runtime_contract_fix as contract_module
from src.platform.display_f3_physical_learning_policy import (
    avaliar_evidencia_energia_check_pelas_mascaras_f3,
)


F3_DIRECT_POWER_SOURCE = "f3_current_frame_check_vs_off_power_gate"
F3_DIRECT_POWER_MIN_RATIO_OVERRIDE_OFF = 0.80
F3_DIRECT_POWER_PROBE_INTERVAL_S = 0.18


def resumir_evidencia_energia_direta_display_f3(evidence: dict | None) -> dict:
    data = evidence if isinstance(evidence, dict) else {}
    try:
        powered = max(0, int(data.get("powered_votes", 0) or 0))
        off = max(0, int(data.get("off_votes", 0) or 0))
        valid = max(0, int(data.get("valid_votes", powered + off) or 0))
        expected_on = max(0, int(data.get("expected_on_mask_count", 0) or 0))
    except (TypeError, ValueError):
        return {
            "available": False,
            "strong": False,
            "reason": "evidencia_invalida",
        }

    if valid <= 0:
        return {
            "available": False,
            "strong": False,
            "expected_on": expected_on,
            "powered_votes": powered,
            "off_votes": off,
            "valid_votes": valid,
            "powered_ratio": 0.0,
            "reason": "sem_votos_validos",
        }

    ratio = powered / float(valid)
    strong = bool(
        data.get("available")
        and expected_on > 0
        and powered > off
        and ratio >= F3_DIRECT_POWER_MIN_RATIO_OVERRIDE_OFF
    )
    return {
        "available": bool(data.get("available")),
        "strong": strong,
        "expected_on": expected_on,
        "powered_votes": powered,
        "off_votes": off,
        "valid_votes": valid,
        "powered_ratio": round(float(ratio), 4),
        "off_confirmed": bool(data.get("off_confirmed")),
    }


def evidencia_direta_confirma_display_ligado_f3(evidence: dict | None) -> bool:
    return bool(resumir_evidencia_energia_direta_display_f3(evidence).get("strong"))


def _rearme_fisico_ativo(app) -> bool:
    return bool(
        getattr(app, "_display_f3_waiting_empty_rearm", False)
        or getattr(app, "_display_f3_waiting_new_board_after_empty", False)
    )


def _evidencia_direta_com_throttle(
    app,
    *,
    repository,
    matcher,
    frame,
    project_name: str,
    check_id: str,
) -> dict:
    now = time.perf_counter()
    signature = (str(project_name), str(check_id))
    previous_signature = getattr(app, "_display_f3_direct_power_signature", None)
    previous_at = float(getattr(app, "_display_f3_direct_power_at", 0.0) or 0.0)
    previous = getattr(app, "_display_f3_direct_power_evidence", None)

    if (
        signature == previous_signature
        and isinstance(previous, dict)
        and now - previous_at < F3_DIRECT_POWER_PROBE_INTERVAL_S
    ):
        return deepcopy(previous)

    try:
        evidence = avaliar_evidencia_energia_check_pelas_mascaras_f3(
            repository=repository,
            matcher=matcher,
            frame=frame,
            project_name=project_name,
            check_id=check_id,
        )
    except Exception as exc:
        evidence = {
            "available": False,
            "off_confirmed": False,
            "reason": "erro_sonda_energia_direta",
            "error": str(exc),
        }

    app._display_f3_direct_power_signature = signature
    app._display_f3_direct_power_at = now
    app._display_f3_direct_power_evidence = deepcopy(evidence)
    return evidence


def promover_falso_off_por_energia_direta_f3(
    state: dict | None,
    *,
    context: dict | None,
    evidence: dict | None,
) -> dict:
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "").strip().lower() != "off":
        return result

    summary = resumir_evidencia_energia_direta_display_f3(evidence)
    result["direct_power_mask_evidence"] = deepcopy(evidence)
    result["direct_power_summary"] = summary
    if not bool(summary.get("strong")):
        return result

    expected_id = str((context or {}).get("check_id") or "").strip()
    if not expected_id:
        return result
    expected_name = str(
        (context or {}).get("check_name") or expected_id or "CHECK"
    ).strip().upper()

    result.update(
        {
            "kind": "powered",
            "text": f"PLACA NO SUPORTE • LIGADA • ANALISANDO {expected_name}",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
            "allow_auto": True,
            "physical_state_key": "check:powered",
            "expected_check_id": expected_id,
            "physical_matches_expected_check": False,
            "powered_board_confirmed": True,
            "source": F3_DIRECT_POWER_SOURCE,
            contract_module.F3_DECISION_ALLOWED_KEY: True,
            contract_module.F3_MASK_LIVE_KEY: True,
        }
    )
    return result


_INSTALLED = False


def instalar_correcao_deadlock_energia_display_f3() -> None:
    """Instala a sonda direta depois do gate físico existente do F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    previous_builder = physical_policy_module._build_physical_operational_state

    def physical_builder(self, frame, project_name: str, context: dict | None):
        state = previous_builder(self, frame, project_name, context)
        if str(state.get("kind") or "").strip().lower() != "off":
            return state
        if _rearme_fisico_ativo(self):
            return state

        check_id = str((context or {}).get("check_id") or "").strip()
        if not check_id:
            return state

        repository = getattr(self, "display_project_repository", None)
        matcher = getattr(self, "_display_f3_operational_matcher", None)
        if repository is None or matcher is None:
            return state

        evidence = _evidencia_direta_com_throttle(
            self,
            repository=repository,
            matcher=matcher,
            frame=frame,
            project_name=project_name,
            check_id=check_id,
        )
        return promover_falso_off_por_energia_direta_f3(
            state,
            context=context,
            evidence=evidence,
        )

    physical_policy_module._build_physical_operational_state = physical_builder
    physical_policy_module._display_f3_direct_power_deadlock_fix_installed = True

    # Se o operacional ainda apontava para o mesmo builder, preserva a coerência.
    if operational_module._build_operational_state is previous_builder:
        operational_module._build_operational_state = physical_builder

    _INSTALLED = True
