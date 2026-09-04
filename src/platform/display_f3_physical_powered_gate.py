from __future__ import annotations

"""Reconcilia presença física e energia óptica no Display F3.

A referência de SUPORTE VAZIO e a referência de PLACA DESLIGADA continuam sendo
as autoridades para presença. As fotos H1/BLUE/USB/AUX ajudam no diagnóstico,
mas uma ROI apertada do display pode ter SSIM baixo mesmo quando a placa está
claramente ligada. Nesse caso, o estado físico não deve ficar eternamente em
UNKNOWN e bloquear o analisador das máscaras.

Esta camada usa a análise semântica já calculada no frame anterior do mesmo
CHECK. Portanto não adiciona leitura de JPEG, SSIM ou extração de features ao
caminho crítico. Quando uma maioria forte das máscaras que deveriam estar ACESAS
foi realmente classificada como ACESA/POUCA LUZ e a cena confirma que há placa
no suporte, o estado físico passa a PLACA LIGADA. Isso libera a análise do CHECK,
mas não declara H1/BLUE/USB/AUX como OK: a conformidade completa continua sendo
responsabilidade do analisador de máscaras.
"""

from copy import deepcopy
from math import ceil

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
import src.platform.display_f3_runtime_contract_fix as contract_module
from src.platform.display_project_repository import DISPLAY_CHECK_STATE_ON


F3_POWERED_STATE_SOURCE = "f3_board_powered_by_presence_and_live_masks"
F3_POWERED_PHYSICAL_KEY = "check:powered"

# A referência OFF também funciona como evidência de que a própria placa está
# ocupando o suporte. Não exigimos que ela passe o threshold de PLACA DESLIGADA,
# pois quando o display liga a região naturalmente muda.
F3_POWERED_MIN_BOARD_SCENE_SCORE = 0.40
F3_POWERED_MIN_OFF_OVER_EMPTY_MARGIN = 0.08

# UNKNOWN -> LIGADA pode usar maioria forte. Para derrubar um OFF explícito a
# evidência precisa ser ainda mais forte, evitando que reflexos isolados liguem a
# placa virtualmente.
F3_POWERED_MIN_RATIO_UNKNOWN = 0.60
F3_POWERED_MIN_RATIO_OVERRIDE_OFF = 0.80
F3_POWERED_MIN_EXPECTED_ON = 1


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resumir_evidencia_ligada_das_mascaras_f3(
    analysis: dict | None,
    context: dict | None,
) -> dict:
    """Resume somente máscaras que o CHECK atual espera ACESAS.

    O resumo não decide OK/NG do CHECK. Ele responde apenas à pergunta física:
    existe evidência óptica suficiente de que o display está energizado?
    """
    if not isinstance(analysis, dict) or not isinstance(context, dict):
        return {"available": False, "strong": False, "reason": "analise_ausente"}
    if not bool(analysis.get("ready")):
        return {"available": False, "strong": False, "reason": "analise_nao_pronta"}

    project_name = str(context.get("project_name") or "")
    check_id = str(context.get("check_id") or "")
    if (
        str(analysis.get("project_name") or "") != project_name
        or str(analysis.get("check_id") or "") != check_id
    ):
        return {
            "available": False,
            "strong": False,
            "reason": "analise_de_outro_check",
        }

    expected_on = [
        item
        for item in (analysis.get("mask_results") or [])
        if isinstance(item, dict)
        and str(item.get("expected") or "") == DISPLAY_CHECK_STATE_ON
    ]
    if len(expected_on) < F3_POWERED_MIN_EXPECTED_ON:
        return {
            "available": False,
            "strong": False,
            "reason": "check_sem_mascara_acesa",
            "expected_on": len(expected_on),
        }

    powered = 0
    off = 0
    other = 0
    details = []
    for item in expected_on:
        classified = str(item.get("classified") or "").strip().lower()
        if classified in {DISPLAY_CHECK_STATE_ON, "low_light"}:
            powered += 1
            vote = "powered"
        elif classified == "off":
            off += 1
            vote = "off"
        else:
            other += 1
            vote = "unknown"
        details.append(
            {
                "mask_id": str(item.get("mask_id") or ""),
                "classified": classified,
                "confidence": _safe_float(item.get("confidence")),
                "vote": vote,
            }
        )

    valid = powered + off
    ratio = (powered / float(valid)) if valid > 0 else 0.0
    minimum_votes = max(1, int(ceil(max(1, valid) * F3_POWERED_MIN_RATIO_UNKNOWN)))
    strong = bool(
        valid > 0
        and powered >= minimum_votes
        and powered > off
    )
    return {
        "available": bool(valid),
        "strong": strong,
        "expected_on": len(expected_on),
        "powered_votes": int(powered),
        "off_votes": int(off),
        "other_votes": int(other),
        "valid_votes": int(valid),
        "powered_ratio": round(float(ratio), 4),
        "details": details,
    }


def avaliar_presenca_da_placa_pelos_scores_f3(state: dict | None) -> dict:
    """Usa OFF x EMPTY apenas para responder se há placa ocupando o suporte."""
    result = state if isinstance(state, dict) else {}
    scores = result.get("reference_scores")
    if not isinstance(scores, dict):
        return {
            "available": False,
            "board_present": False,
            "reason": "scores_ausentes",
        }

    off_score = _safe_float(scores.get("off"))
    empty_score = _safe_float(scores.get("empty"))
    if off_score is None or empty_score is None:
        return {
            "available": False,
            "board_present": False,
            "off_score": off_score,
            "empty_score": empty_score,
            "reason": "scores_presenca_incompletos",
        }

    margin = float(off_score - empty_score)
    board_present = bool(
        off_score >= F3_POWERED_MIN_BOARD_SCENE_SCORE
        and margin >= F3_POWERED_MIN_OFF_OVER_EMPTY_MARGIN
    )
    return {
        "available": True,
        "board_present": board_present,
        "off_score": round(float(off_score), 4),
        "empty_score": round(float(empty_score), 4),
        "off_over_empty_margin": round(margin, 4),
        "minimum_off_score": F3_POWERED_MIN_BOARD_SCENE_SCORE,
        "minimum_margin": F3_POWERED_MIN_OFF_OVER_EMPTY_MARGIN,
    }


def resolver_estado_ligado_f3(
    state: dict | None,
    *,
    context: dict | None,
    analysis: dict | None,
) -> dict:
    """Promove UNKNOWN/falso OFF para PLACA LIGADA sem aprovar o CHECK."""
    result = deepcopy(state) if isinstance(state, dict) else {}
    kind = str(result.get("kind") or "unknown").strip().lower()

    # Suporte vazio, referência indisponível e CHECK físico explícito permanecem
    # absolutos. CHECK diferente do esperado não é escondido por esta camada.
    if kind in {"empty", "unavailable", "check"}:
        return result
    if kind not in {"unknown", "off", "powered"}:
        return result

    mask_evidence = resumir_evidencia_ligada_das_mascaras_f3(analysis, context)
    scene_evidence = avaliar_presenca_da_placa_pelos_scores_f3(result)

    if not bool(mask_evidence.get("available")):
        result["powered_mask_evidence"] = mask_evidence
        return result

    powered_ratio = _safe_float(mask_evidence.get("powered_ratio"), 0.0) or 0.0
    if kind == "off":
        strong_enough = bool(
            mask_evidence.get("strong")
            and powered_ratio >= F3_POWERED_MIN_RATIO_OVERRIDE_OFF
        )
        # OFF já prova que existe placa no suporte; aqui só precisamos decidir se
        # ela está realmente energizada apesar da semelhança global com OFF.
        board_present = True
    else:
        strong_enough = bool(mask_evidence.get("strong"))
        board_present = bool(scene_evidence.get("board_present"))

    if not strong_enough or not board_present:
        result["powered_mask_evidence"] = mask_evidence
        result["board_presence_evidence"] = scene_evidence
        return result

    expected_id = str((context or {}).get("check_id") or "")
    expected_name = str(
        (context or {}).get("check_name")
        or expected_id
        or "CHECK"
    ).strip().upper()

    result.update(
        {
            "kind": "powered",
            "text": (
                "PLACA NO SUPORTE • LIGADA • "
                f"ANALISANDO {expected_name}"
            ),
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
            "allow_auto": True,
            "physical_state_key": F3_POWERED_PHYSICAL_KEY,
            "expected_check_id": expected_id,
            "physical_matches_expected_check": False,
            "powered_board_confirmed": True,
            "source": F3_POWERED_STATE_SOURCE,
            "powered_mask_evidence": mask_evidence,
            "board_presence_evidence": scene_evidence,
            contract_module.F3_DECISION_ALLOWED_KEY: True,
            contract_module.F3_MASK_LIVE_KEY: True,
        }
    )
    return result


def _install_powered_physical_builder() -> None:
    current_physical_builder = physical_policy_module._build_physical_operational_state
    if bool(
        getattr(
            physical_policy_module,
            "_display_f3_powered_physical_builder_installed",
            False,
        )
    ):
        return

    def physical_builder(self, frame, project_name: str, context: dict | None):
        state = current_physical_builder(self, frame, project_name, context)
        analysis = getattr(self, "_display_auto_last_analysis", None)
        return resolver_estado_ligado_f3(
            state,
            context=context,
            analysis=analysis,
        )

    physical_policy_module._build_physical_operational_state = physical_builder
    physical_policy_module._display_f3_powered_physical_builder_installed = True

    # Mantém consultas operacionais paralelas coerentes quando apontavam para o
    # mesmo builder. O runtime principal usa physical_policy_module acima.
    try:
        current_operational_builder = operational_module._build_operational_state
    except Exception:
        current_operational_builder = None

    if current_operational_builder is current_physical_builder:
        operational_module._build_operational_state = physical_builder


def instalar_gate_placa_ligada_display_f3() -> None:
    """Última reconciliação física, exclusiva do F3."""
    _install_powered_physical_builder()
