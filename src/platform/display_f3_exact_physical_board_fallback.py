from __future__ import annotations

"""Fallback físico final OFF/EMPTY para o classificador exato do Display F3.

O runtime produtivo atual e o DEBUG TÉCNICO usam
``display_f3_exact_check_template.classificar_estado_fisico_por_gabaritos_f3``.
O fallback relativo que já existia em ``display_f3_check_transition_guard`` não
atingia esse caminho, portanto cenas de SUPORTE VAZIO/OFF podiam continuar em
IDENTIFICANDO mesmo quando uma das duas referências físicas dominava claramente.

Esta camada reaproveita apenas os scores que o classificador exato já calculou;
não lê imagens novamente e não executa uma segunda análise de visão computacional.
CHECKS continuam dependentes do threshold normal. Somente OFF/EMPTY podem usar a
decisão relativa já validada no F3.
"""

from copy import deepcopy

import src.platform.display_f3_check_transition_guard as transition_module
import src.platform.display_f3_exact_check_template as exact_module
import src.platform.display_f3_operational_status as operational_module


F3_EXACT_BOARD_FALLBACK_SOURCE = "f3_exact_physical_board_relative_fallback"


def aplicar_fallback_fisico_exato_off_empty_f3(state: dict | None) -> dict:
    """Resolve UNKNOWN para OFF/EMPTY usando somente os scores já calculados.

    Não atua em ambiguidade entre candidatos que já passaram o threshold e nunca
    promove H1/BLUE/USB/AUX. A política numérica é a mesma função compartilhada
    pelo classificador físico legado, evitando regras específicas por CHECK.
    """
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "").strip().lower() != "unknown":
        return result
    if bool(result.get("ambiguous")):
        return result
    if not bool(result.get("board_references_complete")):
        return result

    scores = result.get("reference_scores")
    if not isinstance(scores, dict) or not scores:
        return result

    prepared: list[dict] = []
    for raw_key, raw_score in scores.items():
        key = str(raw_key or "").strip()
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if key == "empty":
            kind = "empty"
        elif key == "off":
            kind = "off"
        elif key.startswith("check:"):
            kind = "check"
        else:
            continue
        prepared.append({"key": key, "kind": kind, "score": score})

    winner = transition_module._fallback_estado_fisico_por_dominancia_referencias_f3(
        prepared,
        True,
    )
    if not isinstance(winner, dict):
        return result

    kind = str(winner.get("kind") or "").strip().lower()
    if kind not in {"empty", "off"}:
        return result

    result.update(
        kind=kind,
        allow_auto=False,
        physical_state_key=str(winner.get("key") or kind),
        score=float(winner.get("score") or 0.0),
        physical_low_score_fallback=True,
        physical_low_score_fallback_source=F3_EXACT_BOARD_FALLBACK_SOURCE,
    )
    for key in (
        "physical_low_score_fallback_margin",
        "physical_low_score_fallback_ratio",
        "physical_low_score_best_check_score",
        "physical_low_score_check_margin",
    ):
        if key in winner:
            result[key] = winner[key]

    if kind == "empty":
        result.update(
            text="PLACA FORA DO SUPORTE",
            color=operational_module.F3_OPERATIONAL_STATUS_COLORS["empty"],
        )
    else:
        result.update(
            text="PLACA NO SUPORTE • DESLIGADA",
            color=operational_module.F3_OPERATIONAL_STATUS_COLORS["off"],
        )
    return result


_INSTALLED = False


def instalar_fallback_fisico_exato_off_empty_display_f3() -> None:
    """Instala o fallback no classificador que realmente alimenta runtime/debug."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_classifier = exact_module.classificar_estado_fisico_por_gabaritos_f3

    def classifier(matcher, frame, project_name: str) -> dict:
        state = original_classifier(matcher, frame, project_name)
        return aplicar_fallback_fisico_exato_off_empty_f3(state)

    exact_module.classificar_estado_fisico_por_gabaritos_f3 = classifier
    exact_module.F3_EXACT_PHYSICAL_BOARD_FALLBACK_SOURCE = F3_EXACT_BOARD_FALLBACK_SOURCE
    _INSTALLED = True
