from __future__ import annotations

"""Fallback relativo para a ANÁLISE VISUAL informativa do Display F3.

A análise visual compara somente as duas referências físicas do projeto:
- PLACA FORA DO SUPORTE;
- PLACA DESLIGADA NO SUPORTE.

O limiar absoluto continua sendo a primeira autoridade. Quando nenhuma das duas
referências atinge esse limiar, mas uma delas é claramente dominante, esta camada
permite publicar o estado visual por comparação relativa. Isso corrige variações
de iluminação/exposição sem reduzir globalmente os thresholds das referências.

Esta camada é exclusivamente informativa. Não usa máscaras, não lê estado de
CHECK, não registra OK/NG, não avança sequência e não interfere no F2.
"""

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_snapshot_debug_lightweight_ui as debug_ui
import src.platform.display_visual_reference_status as visual_status_module
from src.platform.display_visual_reference_status import (
    DISPLAY_PROJECT_REFERENCE_BOARD_OFF,
    DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT,
    DISPLAY_PROJECT_REFERENCE_TYPES,
    DisplayVisualReferenceMatcher,
)


F3_VISUAL_RELATIVE_MIN_BEST_SCORE = 0.40
F3_VISUAL_RELATIVE_MIN_MARGIN = 0.12
F3_VISUAL_RELATIVE_MIN_RATIO = 1.50


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolver_analise_visual_relativa_f3(
    empty_candidate: dict | None,
    off_candidate: dict | None,
) -> dict:
    """Resolve as duas referências sem confundir threshold com separação visual."""
    empty = empty_candidate if isinstance(empty_candidate, dict) else {}
    off = off_candidate if isinstance(off_candidate, dict) else {}
    empty_score = _safe_float(empty.get("score"))
    off_score = _safe_float(off.get("score"))

    if empty_score is None or off_score is None:
        return {
            "result_kind": "unidentified",
            "selected_reference": None,
            "decision_mode": "insufficient_scores",
            "relative_fallback": False,
            "best_reference": None,
            "best_score": None,
            "rival_score": None,
            "score_margin": None,
            "score_ratio": None,
        }

    empty_matched = bool(empty.get("matched"))
    off_matched = bool(off.get("matched"))
    margin = abs(empty_score - off_score)

    if empty_score >= off_score:
        best_reference = "empty_support"
        best_score = empty_score
        rival_score = off_score
    else:
        best_reference = "board_off"
        best_score = off_score
        rival_score = empty_score

    ratio = best_score / max(rival_score, 1e-6)

    if empty_matched and off_matched:
        if margin < operational_module.F3_OPERATIONAL_PHYSICAL_MARGIN:
            return {
                "result_kind": "ambiguous",
                "selected_reference": None,
                "decision_mode": "absolute_threshold_ambiguous",
                "relative_fallback": False,
                "best_reference": best_reference,
                "best_score": best_score,
                "rival_score": rival_score,
                "score_margin": margin,
                "score_ratio": ratio,
            }
        selected = best_reference
        return {
            "result_kind": selected,
            "selected_reference": selected,
            "decision_mode": "absolute_threshold",
            "relative_fallback": False,
            "best_reference": best_reference,
            "best_score": best_score,
            "rival_score": rival_score,
            "score_margin": margin,
            "score_ratio": ratio,
        }

    if empty_matched:
        return {
            "result_kind": "empty_support",
            "selected_reference": "empty_support",
            "decision_mode": "absolute_threshold",
            "relative_fallback": False,
            "best_reference": best_reference,
            "best_score": best_score,
            "rival_score": rival_score,
            "score_margin": margin,
            "score_ratio": ratio,
        }

    if off_matched:
        return {
            "result_kind": "board_off",
            "selected_reference": "board_off",
            "decision_mode": "absolute_threshold",
            "relative_fallback": False,
            "best_reference": best_reference,
            "best_score": best_score,
            "rival_score": rival_score,
            "score_margin": margin,
            "score_ratio": ratio,
        }

    relative_ok = bool(
        best_score >= F3_VISUAL_RELATIVE_MIN_BEST_SCORE
        and margin >= F3_VISUAL_RELATIVE_MIN_MARGIN
        and ratio >= F3_VISUAL_RELATIVE_MIN_RATIO
    )
    if relative_ok:
        return {
            "result_kind": best_reference,
            "selected_reference": best_reference,
            "decision_mode": "relative_fallback",
            "relative_fallback": True,
            "best_reference": best_reference,
            "best_score": best_score,
            "rival_score": rival_score,
            "score_margin": margin,
            "score_ratio": ratio,
        }

    return {
        "result_kind": "unidentified",
        "selected_reference": None,
        "decision_mode": "insufficient_relative_separation",
        "relative_fallback": False,
        "best_reference": best_reference,
        "best_score": best_score,
        "rival_score": rival_score,
        "score_margin": margin,
        "score_ratio": ratio,
    }


def _visual_text_from_decision(decision: dict) -> tuple[str, str]:
    kind = str(decision.get("result_kind") or "unidentified")
    score = _safe_float(decision.get("best_score"), 0.0) or 0.0
    relative = bool(decision.get("relative_fallback"))
    suffix = " • comparação relativa" if relative else ""

    if kind == "empty_support":
        return (
            f"ANÁLISE VISUAL: PLACA FORA DO SUPORTE • {score * 100:.0f}%{suffix}",
            operational_module.F3_OPERATIONAL_STATUS_COLORS["empty"],
        )
    if kind == "board_off":
        return (
            f"ANÁLISE VISUAL: PLACA DESLIGADA NO SUPORTE • {score * 100:.0f}%{suffix}",
            operational_module.F3_OPERATIONAL_STATUS_COLORS["off"],
        )
    if kind == "ambiguous":
        return (
            "ANÁLISE VISUAL: referências muito próximas • identificando...",
            operational_module.F3_OPERATIONAL_STATUS_COLORS["unknown"],
        )
    return (
        f"ANÁLISE VISUAL: estado visual não identificado • melhor {score * 100:.0f}%",
        operational_module.F3_OPERATIONAL_STATUS_COLORS["unknown"],
    )


def _build_visual_analysis_state(self, frame, project_name: str) -> dict:
    """Classifica só presença visual; nunca vira autoridade do fluxo produtivo."""
    repository = getattr(self, "display_project_repository", None)
    if repository is None:
        return {
            "text": "ANÁLISE VISUAL: projeto indisponível",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "result_kind": "incomplete",
            "decision_mode": "repository_unavailable",
        }

    matcher = getattr(self, "_display_f3_operational_matcher", None)
    if matcher is None or getattr(matcher, "repository", None) is not repository:
        matcher = DisplayVisualReferenceMatcher(repository)
        self._display_f3_operational_matcher = matcher

    current_small = visual_status_module._small_image(frame)
    if current_small is None:
        return {
            "text": "ANÁLISE VISUAL: aguardando câmera",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "result_kind": "camera_unavailable",
            "decision_mode": "camera_unavailable",
        }

    references = matcher.project_store.get_all(project_name)
    if not all(kind in references for kind in DISPLAY_PROJECT_REFERENCE_TYPES):
        return {
            "text": "ANÁLISE VISUAL: configure as 2 referências do projeto",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "result_kind": "incomplete",
            "decision_mode": "references_incomplete",
        }

    empty_candidate = operational_module._score_candidate(
        matcher,
        current_small,
        references.get(DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT),
    )
    off_candidate = operational_module._score_candidate(
        matcher,
        current_small,
        references.get(DISPLAY_PROJECT_REFERENCE_BOARD_OFF),
    )
    decision = resolver_analise_visual_relativa_f3(empty_candidate, off_candidate)
    text, color = _visual_text_from_decision(decision)
    return {
        "text": text,
        "color": color,
        **decision,
        "informational_only": True,
        "affects_result": False,
        "uses_masks": False,
        "uses_check_state": False,
        "relative_min_best_score": F3_VISUAL_RELATIVE_MIN_BEST_SCORE,
        "relative_min_margin": F3_VISUAL_RELATIVE_MIN_MARGIN,
        "relative_min_ratio": F3_VISUAL_RELATIVE_MIN_RATIO,
    }


def _extend_debug_snapshot(original):
    def build(app, frame, project_name: str):
        snapshot = original(app, frame, project_name)
        if not isinstance(snapshot, dict):
            return snapshot

        candidates = snapshot.get("candidates") if isinstance(snapshot.get("candidates"), dict) else {}
        decision = resolver_analise_visual_relativa_f3(
            candidates.get("empty_support"),
            candidates.get("board_off"),
        )
        snapshot["result_kind"] = decision.get("result_kind")
        snapshot["selected_reference"] = decision.get("selected_reference")
        snapshot["best_reference"] = decision.get("best_reference")
        snapshot["score_margin"] = decision.get("score_margin")
        snapshot["score_ratio"] = decision.get("score_ratio")
        snapshot["decision_mode"] = decision.get("decision_mode")
        snapshot["relative_fallback"] = bool(decision.get("relative_fallback"))
        snapshot["relative_min_best_score"] = F3_VISUAL_RELATIVE_MIN_BEST_SCORE
        snapshot["relative_min_margin"] = F3_VISUAL_RELATIVE_MIN_MARGIN
        snapshot["relative_min_ratio"] = F3_VISUAL_RELATIVE_MIN_RATIO
        return snapshot

    return build


def _extend_debug_report(original):
    def report(snapshot: dict) -> str:
        base = original(snapshot)
        visual = snapshot.get("visual_analysis") if isinstance(snapshot, dict) else None
        if not base or not isinstance(visual, dict):
            return base
        detail = (
            "visual_decision "
            f"| mode={visual.get('decision_mode', '--')} "
            f"| relative_fallback={visual.get('relative_fallback', '--')} "
            f"| score_ratio={debug_ui.manual_module._fmt(visual.get('score_ratio'))} "
            f"| relative_min_best={debug_ui.manual_module._fmt(visual.get('relative_min_best_score'))} "
            f"| relative_min_margin={debug_ui.manual_module._fmt(visual.get('relative_min_margin'))} "
            f"| relative_min_ratio={debug_ui.manual_module._fmt(visual.get('relative_min_ratio'))}"
        )
        return f"{base}\n{detail}"

    return report


_INSTALLED = False


def instalar_fallback_relativo_analise_visual_display_f3() -> None:
    """Instala a mesma decisão relativa no status ao vivo e no Debug Técnico."""
    global _INSTALLED
    if _INSTALLED:
        return

    operational_module._build_visual_analysis_state = _build_visual_analysis_state

    if not bool(getattr(debug_ui, "_display_f3_visual_relative_snapshot_installed", False)):
        debug_ui._build_visual_analysis_snapshot = _extend_debug_snapshot(
            debug_ui._build_visual_analysis_snapshot
        )
        debug_ui._visual_report_block = _extend_debug_report(
            debug_ui._visual_report_block
        )
        debug_ui._display_f3_visual_relative_snapshot_installed = True

    operational_module._display_f3_visual_relative_fallback_installed = True
    _INSTALLED = True
