from __future__ import annotations

"""Análise visual informativa expandida do Display F3.

A leitura visual compara, sobre o frame ao vivo:
- PLACA FORA DO SUPORTE;
- PLACA DESLIGADA NO SUPORTE;
- a foto configurada de cada CHECK do projeto.

Todas as referências são comparadas com ROI primeiro, em resolução cheia. O
resultado serve somente para o status ANÁLISE VISUAL e para o Debug Técnico.
Ele não usa máscaras, não consulta qual CHECK é esperado, não registra OK/NG,
não avança sequência, não rearma ciclo e não interfere no F2.
"""

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_snapshot_debug_lightweight_ui as debug_ui
from src.platform.display_f3_exact_check_template import (
    _physical_candidates,
    _score_reference_full_roi,
)
from src.platform.display_visual_reference_status import (
    DISPLAY_PROJECT_REFERENCE_TYPES,
    DisplayVisualReferenceMatcher,
)


F3_VISUAL_RELATIVE_MIN_BEST_SCORE = 0.40
F3_VISUAL_RELATIVE_MIN_MARGIN = 0.12
F3_VISUAL_RELATIVE_MIN_RATIO = 1.50
F3_VISUAL_RELATIVE_STRONG_MARGIN = 0.16


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_visual_key(candidate: dict) -> str:
    key = str(candidate.get("key") or "").strip()
    if key == "empty":
        return "empty_support"
    if key == "off":
        return "board_off"
    return key


def _result_kind_from_reference(key: str) -> str:
    if key == "empty_support":
        return "empty_support"
    if key == "board_off":
        return "board_off"
    if str(key).startswith("check:"):
        return "check"
    return "unidentified"


def _decision_payload(
    *,
    selected_reference: str | None,
    decision_mode: str,
    relative_fallback: bool,
    best_reference: str | None,
    best_score: float | None,
    rival_score: float | None,
    score_margin: float | None,
    score_ratio: float | None,
    candidate: dict | None = None,
    matched_count: int = 0,
    candidate_count: int = 0,
) -> dict:
    result_kind = (
        _result_kind_from_reference(selected_reference)
        if selected_reference
        else ("ambiguous" if decision_mode.endswith("ambiguous") else "unidentified")
    )
    payload = {
        "result_kind": result_kind,
        "selected_reference": selected_reference,
        "decision_mode": decision_mode,
        "relative_fallback": bool(relative_fallback),
        "best_reference": best_reference,
        "best_score": best_score,
        "rival_score": rival_score,
        "score_margin": score_margin,
        "score_ratio": score_ratio,
        "matched_count": int(matched_count),
        "candidate_count": int(candidate_count),
    }
    if isinstance(candidate, dict):
        payload["selected_name"] = str(candidate.get("name") or "")
        payload["selected_kind"] = str(candidate.get("kind") or "")
        payload["check_id"] = str(candidate.get("check_id") or "")
        payload["check_name"] = str(candidate.get("name") or "") if str(candidate.get("kind")) == "check" else ""
    return payload


def resolver_analise_visual_candidatos_f3(
    candidates: dict[str, dict] | None,
) -> dict:
    """Escolhe uma referência visual sem conhecer o CHECK lógico esperado."""
    source = candidates if isinstance(candidates, dict) else {}
    ranked: list[tuple[str, dict, float]] = []
    for key, candidate in source.items():
        if not isinstance(candidate, dict):
            continue
        score = _safe_float(candidate.get("score"))
        if score is None:
            continue
        ranked.append((str(key), candidate, score))

    ranked.sort(key=lambda item: item[2], reverse=True)
    if not ranked:
        return _decision_payload(
            selected_reference=None,
            decision_mode="insufficient_scores",
            relative_fallback=False,
            best_reference=None,
            best_score=None,
            rival_score=None,
            score_margin=None,
            score_ratio=None,
            matched_count=0,
            candidate_count=0,
        )

    matched = [item for item in ranked if bool(item[1].get("matched"))]
    pool = matched if matched else ranked
    best_key, best_candidate, best_score = pool[0]
    second = pool[1] if len(pool) >= 2 else None
    rival_score = second[2] if second is not None else 0.0
    margin = best_score - rival_score
    ratio = best_score / max(rival_score, 1e-6)

    if matched:
        if len(matched) >= 2 and margin < operational_module.F3_OPERATIONAL_PHYSICAL_MARGIN:
            return _decision_payload(
                selected_reference=None,
                decision_mode="absolute_threshold_ambiguous",
                relative_fallback=False,
                best_reference=best_key,
                best_score=best_score,
                rival_score=rival_score,
                score_margin=margin,
                score_ratio=ratio,
                candidate=best_candidate,
                matched_count=len(matched),
                candidate_count=len(ranked),
            )
        return _decision_payload(
            selected_reference=best_key,
            decision_mode="absolute_threshold",
            relative_fallback=False,
            best_reference=best_key,
            best_score=best_score,
            rival_score=rival_score,
            score_margin=margin,
            score_ratio=ratio,
            candidate=best_candidate,
            matched_count=len(matched),
            candidate_count=len(ranked),
        )

    relative_ok = bool(
        best_score >= F3_VISUAL_RELATIVE_MIN_BEST_SCORE
        and margin >= F3_VISUAL_RELATIVE_MIN_MARGIN
        and (
            ratio >= F3_VISUAL_RELATIVE_MIN_RATIO
            or margin >= F3_VISUAL_RELATIVE_STRONG_MARGIN
        )
    )
    if relative_ok:
        return _decision_payload(
            selected_reference=best_key,
            decision_mode="relative_fallback",
            relative_fallback=True,
            best_reference=best_key,
            best_score=best_score,
            rival_score=rival_score,
            score_margin=margin,
            score_ratio=ratio,
            candidate=best_candidate,
            matched_count=0,
            candidate_count=len(ranked),
        )

    return _decision_payload(
        selected_reference=None,
        decision_mode="insufficient_relative_separation",
        relative_fallback=False,
        best_reference=best_key,
        best_score=best_score,
        rival_score=rival_score,
        score_margin=margin,
        score_ratio=ratio,
        candidate=best_candidate,
        matched_count=0,
        candidate_count=len(ranked),
    )


def resolver_analise_visual_relativa_f3(
    empty_candidate: dict | None,
    off_candidate: dict | None,
) -> dict:
    """Compatibilidade: resolve somente as duas referências físicas."""
    return resolver_analise_visual_candidatos_f3(
        {
            "empty_support": empty_candidate or {},
            "board_off": off_candidate or {},
        }
    )


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
    if kind == "check":
        name = str(
            decision.get("check_name")
            or decision.get("selected_name")
            or decision.get("check_id")
            or "CHECK"
        ).strip().upper()
        return (
            f"ANÁLISE VISUAL: CHECK {name} • {score * 100:.0f}%{suffix}",
            operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
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


def _collect_visual_candidates(
    matcher: DisplayVisualReferenceMatcher,
    frame,
    project_name: str,
) -> dict[str, dict]:
    """Pontua referências físicas e CHECKS com ROI-first em resolução cheia."""
    result: dict[str, dict] = {}
    for source in _physical_candidates(matcher, project_name):
        metadata = source.get("metadata")
        if not isinstance(metadata, dict):
            continue
        score = _score_reference_full_roi(frame, metadata)
        if score is None:
            continue
        key = _normalized_visual_key(source)
        threshold = float(matcher._threshold(metadata))
        kind = str(source.get("kind") or "")
        item = {
            "key": key,
            "kind": (
                "empty_support"
                if key == "empty_support"
                else "board_off"
                if key == "board_off"
                else kind
            ),
            "name": str(source.get("name") or key),
            "configured": True,
            "score": float(score),
            "threshold": threshold,
            "matched": float(score) >= threshold,
            "margin_to_threshold": round(float(score) - threshold, 6),
            "roi": dict(metadata.get("roi") or {})
            if isinstance(metadata.get("roi"), dict)
            else None,
            "image_path": str(metadata.get("image_path") or ""),
            "comparison_mode": "full_resolution_roi_first",
            "error": None,
        }
        if kind == "check":
            item["check_id"] = str(source.get("check_id") or "")
            item["check_name"] = str(source.get("name") or source.get("check_id") or "")
        result[key] = item
    return result


def _project_references_complete(
    matcher: DisplayVisualReferenceMatcher,
    project_name: str,
) -> bool:
    references = matcher.project_store.get_all(project_name)
    return all(kind in references for kind in DISPLAY_PROJECT_REFERENCE_TYPES)


def _build_visual_analysis_state(self, frame, project_name: str) -> dict:
    """Classifica somente a cena visual; nunca vira autoridade produtiva."""
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

    if frame is None or getattr(frame, "size", 0) == 0:
        return {
            "text": "ANÁLISE VISUAL: aguardando câmera",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "result_kind": "camera_unavailable",
            "decision_mode": "camera_unavailable",
        }

    if not _project_references_complete(matcher, project_name):
        return {
            "text": "ANÁLISE VISUAL: configure as 2 referências físicas do projeto",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "result_kind": "incomplete",
            "decision_mode": "references_incomplete",
        }

    candidates = _collect_visual_candidates(matcher, frame, project_name)
    decision = resolver_analise_visual_candidatos_f3(candidates)
    text, color = _visual_text_from_decision(decision)
    check_reference_count = sum(
        1 for item in candidates.values() if str(item.get("kind")) == "check"
    )
    return {
        "text": text,
        "color": color,
        **decision,
        "candidates": candidates,
        "informational_only": True,
        "affects_result": False,
        "uses_masks": False,
        "uses_check_state": False,
        "uses_check_references": True,
        "analysis_type": "all_configured_visual_references",
        "comparison_basis": "full_resolution_roi_first",
        "check_reference_count": check_reference_count,
        "relative_min_best_score": F3_VISUAL_RELATIVE_MIN_BEST_SCORE,
        "relative_min_margin": F3_VISUAL_RELATIVE_MIN_MARGIN,
        "relative_min_ratio": F3_VISUAL_RELATIVE_MIN_RATIO,
        "relative_strong_margin": F3_VISUAL_RELATIVE_STRONG_MARGIN,
    }


def _extend_debug_snapshot(original):
    def build(app, frame, project_name: str):
        snapshot = original(app, frame, project_name)
        if not isinstance(snapshot, dict):
            return snapshot

        repository = getattr(app, "display_project_repository", None)
        if repository is None:
            return snapshot
        matcher = DisplayVisualReferenceMatcher(repository)
        candidates = _collect_visual_candidates(matcher, frame, project_name)
        decision = resolver_analise_visual_candidatos_f3(candidates)
        text, color = _visual_text_from_decision(decision)

        snapshot["available"] = bool(candidates)
        snapshot["informational_only"] = True
        snapshot["affects_result"] = False
        snapshot["uses_masks"] = False
        snapshot["uses_check_state"] = False
        snapshot["uses_check_references"] = True
        snapshot["analysis_type"] = "all_configured_visual_references"
        snapshot["comparison_basis"] = "full_resolution_roi_first"
        snapshot["status_text"] = text
        snapshot["status_color"] = color
        snapshot["candidates"] = candidates
        snapshot["result_kind"] = decision.get("result_kind")
        snapshot["selected_reference"] = decision.get("selected_reference")
        snapshot["best_reference"] = decision.get("best_reference")
        snapshot["best_score"] = decision.get("best_score")
        snapshot["rival_score"] = decision.get("rival_score")
        snapshot["score_margin"] = decision.get("score_margin")
        snapshot["score_ratio"] = decision.get("score_ratio")
        snapshot["decision_mode"] = decision.get("decision_mode")
        snapshot["relative_fallback"] = bool(decision.get("relative_fallback"))
        snapshot["check_id"] = decision.get("check_id")
        snapshot["check_name"] = decision.get("check_name")
        snapshot["check_reference_count"] = sum(
            1 for item in candidates.values() if str(item.get("kind")) == "check"
        )
        snapshot["relative_min_best_score"] = F3_VISUAL_RELATIVE_MIN_BEST_SCORE
        snapshot["relative_min_margin"] = F3_VISUAL_RELATIVE_MIN_MARGIN
        snapshot["relative_min_ratio"] = F3_VISUAL_RELATIVE_MIN_RATIO
        snapshot["relative_strong_margin"] = F3_VISUAL_RELATIVE_STRONG_MARGIN
        return snapshot

    return build


def _extend_debug_report(original):
    def report(snapshot: dict) -> str:
        base = original(snapshot)
        visual = snapshot.get("visual_analysis") if isinstance(snapshot, dict) else None
        if not base or not isinstance(visual, dict):
            return base

        lines = [
            (
                "visual_decision "
                f"| mode={visual.get('decision_mode', '--')} "
                f"| relative_fallback={visual.get('relative_fallback', '--')} "
                f"| score_ratio={debug_ui.manual_module._fmt(visual.get('score_ratio'))} "
                f"| relative_min_best={debug_ui.manual_module._fmt(visual.get('relative_min_best_score'))} "
                f"| relative_min_margin={debug_ui.manual_module._fmt(visual.get('relative_min_margin'))} "
                f"| relative_min_ratio={debug_ui.manual_module._fmt(visual.get('relative_min_ratio'))} "
                f"| relative_strong_margin={debug_ui.manual_module._fmt(visual.get('relative_strong_margin'))}"
            ),
            (
                "visual_scope "
                f"| check_references={visual.get('check_reference_count', 0)} "
                f"| uses_check_references={visual.get('uses_check_references', False)} "
                f"| uses_check_state={visual.get('uses_check_state', False)} "
                f"| comparison={visual.get('comparison_basis', '--')}"
            ),
        ]

        candidates = visual.get("candidates")
        if isinstance(candidates, dict):
            checks = [
                (key, value)
                for key, value in candidates.items()
                if isinstance(value, dict) and str(value.get("kind")) == "check"
            ]
            checks.sort(
                key=lambda item: _safe_float(item[1].get("score"), -1.0),
                reverse=True,
            )
            for key, candidate in checks:
                lines.append(
                    "visual_check_reference "
                    + " | ".join(
                        (
                            f"key={key}",
                            f"name={candidate.get('name', '--')}",
                            f"check_id={candidate.get('check_id', '--')}",
                            f"matched={candidate.get('matched', '--')}",
                            f"score={debug_ui.manual_module._fmt(candidate.get('score'))}",
                            f"threshold={debug_ui.manual_module._fmt(candidate.get('threshold'))}",
                            f"margin_threshold={debug_ui.manual_module._fmt(candidate.get('margin_to_threshold'))}",
                            f"roi={candidate.get('roi', '--')}",
                            f"path={candidate.get('image_path', '--')}",
                        )
                    )
                )
        return f"{base}\n" + "\n".join(lines)

    return report


_INSTALLED = False


def instalar_fallback_relativo_analise_visual_display_f3() -> None:
    """Instala a análise visual completa no status ao vivo e no Debug Técnico."""
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
    operational_module._display_f3_visual_check_references_installed = True
    _INSTALLED = True
