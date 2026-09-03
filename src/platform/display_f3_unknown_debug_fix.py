from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import tkinter as tk
from collections.abc import Callable

import src.platform.display_auto_check_runtime as auto_runtime_module
import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
import src.platform.display_visual_reference_status as visual_status_module
from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.display_visual_reference_status import (
    DISPLAY_PROJECT_REFERENCE_BOARD_OFF,
    DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT,
    DISPLAY_PROJECT_REFERENCE_TYPES,
)


# O classificador global usa limiar 0.72 por padrão. Em produção, pequenas
# variações de exposição/balanço de branco podem derrubar o SSIM global sem que
# exista dúvida real entre PLACA DESLIGADA e SUPORTE VAZIO. Este fallback nunca
# liga o automático: ele serve somente para tirar o estado físico de UNKNOWN e
# confirmar OFF quando duas evidências independentes concordam.
F3_UNKNOWN_OFF_MIN_SCORE = 0.55
F3_UNKNOWN_OFF_MIN_THRESHOLD_RATIO = 0.80
F3_UNKNOWN_OFF_MIN_EMPTY_MARGIN = 0.035
F3_UNKNOWN_OFF_STABLE_FRAMES = 2
F3_UNKNOWN_OFF_SOURCE = "f3_unknown_off_by_board_presence_and_expected_on_masks"


DEBUG_BG = "#07111F"
DEBUG_PANEL = "#0B1220"
DEBUG_BORDER = "#334155"
DEBUG_TEXT = "#E2E8F0"
DEBUG_MUTED = "#94A3B8"
DEBUG_ACTION = "#0E7490"
DEBUG_ACTION_ACTIVE = "#0891B2"


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_float(value) -> str:
    number = _safe_float(value)
    return "--" if number is None else f"{number:.4f}"


def _fmt_bool(value) -> str:
    return "SIM" if bool(value) else "NÃO"


def resolver_unknown_com_evidencia_off_f3(
    state: dict | None,
    *,
    evidence: dict | None,
    off_score: float | None,
    off_threshold: float | None,
    empty_score: float | None,
    board_references_complete: bool,
) -> dict:
    """Resolve UNKNOWN como OFF somente com presença + máscaras concordantes.

    Regras de segurança:
    - nunca altera EMPTY, OFF, CHECK ou UNAVAILABLE;
    - exige as duas referências de presença do projeto;
    - exige votação forte das máscaras que deveriam estar ACESAS no CHECK atual;
    - exige que a cena inteira se pareça mais com PLACA DESLIGADA que SUPORTE VAZIO;
    - aceita uma queda moderada abaixo do threshold para tolerar variação de luz.
    """
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "unknown").strip().lower() != "unknown":
        return result

    evidence_data = deepcopy(evidence) if isinstance(evidence, dict) else {}
    score_off = _safe_float(off_score)
    threshold_off = _safe_float(off_threshold)
    score_empty = _safe_float(empty_score)
    minimum_score = max(
        F3_UNKNOWN_OFF_MIN_SCORE,
        (threshold_off or 0.0) * F3_UNKNOWN_OFF_MIN_THRESHOLD_RATIO,
    )

    diagnostics = {
        "board_references_complete": bool(board_references_complete),
        "off_score": score_off,
        "off_threshold": threshold_off,
        "empty_score": score_empty,
        "minimum_off_score": float(minimum_score),
        "minimum_empty_margin": F3_UNKNOWN_OFF_MIN_EMPTY_MARGIN,
        "power_mask_evidence": evidence_data,
    }
    result["unknown_off_diagnostics"] = diagnostics

    if not bool(board_references_complete):
        diagnostics["blocked_reason"] = "referencias_presenca_incompletas"
        return result
    if not bool(evidence_data.get("available")):
        diagnostics["blocked_reason"] = str(
            evidence_data.get("reason") or "evidencia_mascaras_indisponivel"
        )
        return result
    if not bool(evidence_data.get("off_confirmed")):
        diagnostics["blocked_reason"] = "mascaras_nao_confirmam_off"
        return result
    if score_off is None or threshold_off is None or score_empty is None:
        diagnostics["blocked_reason"] = "scores_presenca_indisponiveis"
        return result
    if score_off < minimum_score:
        diagnostics["blocked_reason"] = "score_off_muito_baixo"
        return result
    if score_off < score_empty + F3_UNKNOWN_OFF_MIN_EMPTY_MARGIN:
        diagnostics["blocked_reason"] = "off_nao_supera_suporte_vazio"
        return result

    diagnostics["resolved"] = True
    return {
        **result,
        "kind": "off",
        "text": physical_policy_module.F3_STATUS_BOARD_OFF,
        "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["off"],
        "allow_auto": False,
        "physical_state_key": "off",
        "source": F3_UNKNOWN_OFF_SOURCE,
        "power_mask_evidence": evidence_data,
        "unknown_off_diagnostics": diagnostics,
    }


def _presence_scores(matcher, frame, project_name: str) -> dict:
    current_small = visual_status_module._small_image(frame)
    references = matcher.project_store.get_all(project_name)
    board_complete = all(kind in references for kind in DISPLAY_PROJECT_REFERENCE_TYPES)
    if current_small is None:
        return {
            "board_references_complete": board_complete,
            "off_score": None,
            "off_threshold": None,
            "empty_score": None,
            "empty_threshold": None,
        }

    off_metadata = references.get(DISPLAY_PROJECT_REFERENCE_BOARD_OFF)
    empty_metadata = references.get(DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT)
    off_score = matcher._score(current_small, off_metadata)
    empty_score = matcher._score(current_small, empty_metadata)
    return {
        "board_references_complete": board_complete,
        "off_score": _safe_float(off_score),
        "off_threshold": (
            _safe_float(matcher._threshold(off_metadata))
            if isinstance(off_metadata, dict)
            else None
        ),
        "empty_score": _safe_float(empty_score),
        "empty_threshold": (
            _safe_float(matcher._threshold(empty_metadata))
            if isinstance(empty_metadata, dict)
            else None
        ),
    }


def _same_camera_frame_token(self, frame):
    camera_token = getattr(self, "camera_ultimo_frame_id", None)
    if isinstance(camera_token, int) and camera_token >= 0:
        return ("camera", int(camera_token))
    return ("object", id(frame))


def _confirm_unknown_off_candidate(self, state: dict, frame) -> dict:
    if str(state.get("source") or "") != F3_UNKNOWN_OFF_SOURCE:
        self._display_f3_unknown_off_pending_frames = 0
        self._display_f3_unknown_off_last_token = None
        return state

    token = _same_camera_frame_token(self, frame)
    last_token = getattr(self, "_display_f3_unknown_off_last_token", None)
    frames = int(getattr(self, "_display_f3_unknown_off_pending_frames", 0) or 0)
    if token != last_token:
        frames += 1
        self._display_f3_unknown_off_last_token = token
        self._display_f3_unknown_off_pending_frames = frames

    if frames >= F3_UNKNOWN_OFF_STABLE_FRAMES:
        self._display_f3_unknown_off_pending_frames = 0
        self._display_f3_unknown_off_last_token = None
        result = deepcopy(state)
        result["unknown_off_stable_frames"] = frames
        return result

    diagnostics = deepcopy(state.get("unknown_off_diagnostics") or {})
    diagnostics["pending_frames"] = frames
    diagnostics["required_frames"] = F3_UNKNOWN_OFF_STABLE_FRAMES
    return {
        "kind": "unknown",
        "text": "IDENTIFICANDO PLACA DESLIGADA...",
        "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unknown"],
        "allow_auto": False,
        "board_references_complete": bool(state.get("board_references_complete")),
        "configured_count": int(state.get("configured_count", 0) or 0),
        "unknown_off_fallback_pending": True,
        "unknown_off_diagnostics": diagnostics,
    }


def _resolve_unknown_off_runtime(
    self,
    state: dict | None,
    frame,
    project_name: str,
    context: dict | None,
) -> dict:
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "unknown").strip().lower() != "unknown":
        self._display_f3_unknown_off_pending_frames = 0
        self._display_f3_unknown_off_last_token = None
        return result

    repository = getattr(self, "display_project_repository", None)
    matcher = getattr(self, "_display_f3_operational_matcher", None)
    current_check_id = str((context or {}).get("check_id") or "")
    if repository is None or matcher is None or not current_check_id:
        return result

    try:
        presence = _presence_scores(matcher, frame, project_name)
        evidence = physical_policy_module.avaliar_evidencia_energia_check_pelas_mascaras_f3(
            repository=repository,
            matcher=matcher,
            frame=frame,
            project_name=project_name,
            check_id=current_check_id,
        )
    except Exception as exc:
        result["unknown_off_diagnostics"] = {
            "blocked_reason": "erro_ao_avaliar_fallback",
            "error": f"{type(exc).__name__}: {exc}",
        }
        return result

    candidate = resolver_unknown_com_evidencia_off_f3(
        result,
        evidence=evidence,
        off_score=presence.get("off_score"),
        off_threshold=presence.get("off_threshold"),
        empty_score=presence.get("empty_score"),
        board_references_complete=bool(presence.get("board_references_complete")),
    )
    candidate["unknown_off_presence_scores"] = presence
    return _confirm_unknown_off_candidate(self, candidate, frame)


def _reference_debug_rows(app, frame, project_name: str) -> list[dict]:
    repository = getattr(app, "display_project_repository", None)
    matcher = getattr(app, "_display_f3_operational_matcher", None)
    if repository is None or matcher is None:
        return []
    current_small = visual_status_module._small_image(frame)
    if current_small is None:
        return []

    rows: list[dict] = []
    project_refs = matcher.project_store.get_all(project_name)
    for kind, label in (
        (DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT, "SUPORTE VAZIO"),
        (DISPLAY_PROJECT_REFERENCE_BOARD_OFF, "PLACA DESLIGADA"),
    ):
        metadata = project_refs.get(kind)
        if not isinstance(metadata, dict):
            rows.append({"key": kind, "name": label, "configured": False})
            continue
        score = matcher._score(current_small, metadata)
        threshold = matcher._threshold(metadata)
        rows.append(
            {
                "key": kind,
                "name": label,
                "configured": True,
                "score": _safe_float(score),
                "threshold": _safe_float(threshold),
                "matched": bool(
                    score is not None and float(score) >= float(threshold)
                ),
            }
        )

    try:
        checks = repository.listar_checks(project_name)
    except Exception:
        checks = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        check_id = str(check.get("id") or "")
        if not check_id:
            continue
        metadata = matcher.check_store.get(project_name, check_id)
        name = str(check.get("name") or check_id).strip().upper()
        if not isinstance(metadata, dict):
            rows.append(
                {
                    "key": f"check:{check_id}",
                    "name": name,
                    "configured": False,
                }
            )
            continue
        score = matcher._score(current_small, metadata)
        threshold = matcher._threshold(metadata)
        rows.append(
            {
                "key": f"check:{check_id}",
                "name": name,
                "configured": True,
                "score": _safe_float(score),
                "threshold": _safe_float(threshold),
                "matched": bool(
                    score is not None and float(score) >= float(threshold)
                ),
            }
        )

    return sorted(
        rows,
        key=lambda item: (
            item.get("score") is not None,
            _safe_float(item.get("score"), -1.0),
        ),
        reverse=True,
    )


def _append_mapping(lines: list[str], title: str, data: dict | None, keys: tuple[str, ...]) -> None:
    lines.append(title)
    source = data if isinstance(data, dict) else {}
    for key in keys:
        value = source.get(key)
        if isinstance(value, float):
            value = f"{value:.4f}"
        lines.append(f"{key}={value if value is not None else '--'}")
    lines.append("")


def montar_debug_tecnico_display_f3(app) -> str:
    """Gera texto autocontido para o operador copiar e colar no suporte técnico."""
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    repository = getattr(app, "display_project_repository", None)
    try:
        project_name = str(repository.obter_projeto_ativo() or "") if repository else ""
    except Exception:
        project_name = ""
    try:
        context = app._display_auto_current_context()
    except Exception:
        context = None
    state = getattr(app, "_display_f3_operational_state", None)
    analysis = getattr(app, "_display_auto_last_analysis", None)
    frame = getattr(app, "camera_frame_atual", None)

    frame_shape = getattr(frame, "shape", None)
    frame_text = "--"
    if isinstance(frame_shape, tuple) and len(frame_shape) >= 2:
        frame_text = "x".join(str(int(value)) for value in frame_shape[:3])

    try:
        rotation = int(app._obter_rotacao_visual_display_f3())
    except Exception:
        rotation = int(getattr(app, "visual_rotation", 0) or 0)

    lines = [
        "ODIN DISPLAY F3 - DEBUG TÉCNICO",
        f"gerado_em={now}",
        f"projeto={project_name or '--'}",
        f"config_file={getattr(repository, 'config_file', '--') if repository else '--'}",
        f"camera_frame_id={getattr(app, 'camera_ultimo_frame_id', '--')}",
        f"frame_shape={frame_text}",
        f"visual_rotation={rotation}",
        "",
    ]

    _append_mapping(
        lines,
        "[CHECK LÓGICO]",
        context,
        ("current_index", "check_id", "check_name", "project_name"),
    )

    _append_mapping(
        lines,
        "[ESTADO FÍSICO FINAL]",
        state,
        (
            "kind",
            "text",
            "allow_auto",
            "source",
            "physical_state_key",
            "score",
            "best_score",
            "configured_count",
            "board_references_complete",
            "current_check_reference_configured",
            "physical_transition_pending",
            "pending_physical_state_key",
            "fast_expected_check_gate",
            "physical_matches_expected_check",
        ),
    )

    unknown_diag = (state or {}).get("unknown_off_diagnostics") if isinstance(state, dict) else None
    if isinstance(unknown_diag, dict):
        _append_mapping(
            lines,
            "[FALLBACK UNKNOWN -> OFF]",
            unknown_diag,
            (
                "resolved",
                "blocked_reason",
                "board_references_complete",
                "off_score",
                "off_threshold",
                "empty_score",
                "minimum_off_score",
                "minimum_empty_margin",
                "pending_frames",
                "required_frames",
                "error",
            ),
        )

    lines.append("[REFERÊNCIAS VISUAIS - CÁLCULO SOB DEMANDA]")
    try:
        rows = _reference_debug_rows(app, frame, project_name) if project_name else []
    except Exception as exc:
        rows = []
        lines.append(f"erro={type(exc).__name__}: {exc}")
    if not rows:
        lines.append("nenhuma_referencia_calculavel")
    for row in rows:
        lines.append(
            " | ".join(
                (
                    f"key={row.get('key', '--')}",
                    f"nome={row.get('name', '--')}",
                    f"configurada={_fmt_bool(row.get('configured'))}",
                    f"score={_fmt_float(row.get('score'))}",
                    f"threshold={_fmt_float(row.get('threshold'))}",
                    f"passou={_fmt_bool(row.get('matched'))}",
                )
            )
        )
    lines.append("")

    power = None
    if isinstance(state, dict):
        power = state.get("power_mask_evidence")
        if not isinstance(power, dict) and isinstance(unknown_diag, dict):
            power = unknown_diag.get("power_mask_evidence")
    _append_mapping(
        lines,
        "[EVIDÊNCIA DE ENERGIA NAS MÁSCARAS]",
        power,
        (
            "available",
            "off_confirmed",
            "reason",
            "check_id",
            "expected_on_mask_count",
            "off_votes",
            "powered_votes",
            "tie_votes",
            "valid_votes",
        ),
    )
    for item in (power or {}).get("details", []) if isinstance(power, dict) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            "mask "
            + " | ".join(
                (
                    f"id={item.get('mask_id', '--')}",
                    f"winner={item.get('winner', '--')}",
                    f"d_off={item.get('distance_off', '--')}",
                    f"d_check={item.get('distance_check', '--')}",
                    f"span={item.get('reference_span', '--')}",
                    f"separation={item.get('separation', '--')}",
                )
            )
        )
    if isinstance(power, dict) and power.get("details"):
        lines.append("")

    _append_mapping(
        lines,
        "[ANÁLISE AUTOMÁTICA DO CHECK]",
        analysis,
        (
            "ready",
            "approved",
            "reason",
            "active_mask_count",
            "matched_mask_count",
            "power_evidence",
        ),
    )
    for item in (analysis or {}).get("mask_results", []) if isinstance(analysis, dict) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            "mask "
            + " | ".join(
                (
                    f"id={item.get('mask_id', item.get('id', '--'))}",
                    f"expected={item.get('expected', '--')}",
                    f"classified={item.get('classified', '--')}",
                    f"confidence={_fmt_float(item.get('confidence'))}",
                    f"matched={_fmt_bool(item.get('matched'))}",
                )
            )
        )
    if isinstance(analysis, dict) and analysis.get("mask_results"):
        lines.append("")

    lines.extend(
        [
            "[RUNTIME / DEBOUNCE]",
            f"last_decision={getattr(app, '_display_auto_last_decision', '--')}",
            f"stable_frames={getattr(app, '_display_auto_stable_frames', '--')}",
            f"transition_frames={getattr(app, '_display_auto_transition_frames', '--')}",
            f"physical_stable_key={getattr(app, '_display_f3_physical_stable_key', '--')}",
            f"physical_pending_key={getattr(app, '_display_f3_physical_pending_key', '--')}",
            f"physical_pending_frames={getattr(app, '_display_f3_physical_pending_frames', '--')}",
            f"unknown_off_pending_frames={getattr(app, '_display_f3_unknown_off_pending_frames', '--')}",
            f"manual_entry_signature={getattr(app, '_display_auto_manual_entry_signature', '--')}",
            f"manual_entry_label={getattr(app, '_display_auto_manual_entry_label', '--')}",
            f"waiting_empty_rearm={getattr(app, '_display_f3_waiting_empty_rearm', False)}",
            "",
            "Cole este bloco inteiro no chamado/conversa de debug.",
        ]
    )
    return "\n".join(lines)


def _install_unknown_off_builder() -> None:
    original_physical = physical_policy_module._build_physical_operational_state
    original_operational = operational_module._build_operational_state

    def physical_builder(self, frame, project_name: str, context: dict | None):
        state = original_physical(self, frame, project_name, context)
        return _resolve_unknown_off_runtime(
            self,
            state,
            frame,
            project_name,
            context,
        )

    physical_policy_module._build_physical_operational_state = physical_builder

    if original_operational is original_physical:
        operational_module._build_operational_state = physical_builder
    else:
        def operational_builder(self, frame, project_name: str, context: dict | None):
            state = original_operational(self, frame, project_name, context)
            return _resolve_unknown_off_runtime(
                self,
                state,
                frame,
                project_name,
                context,
            )

        operational_module._build_operational_state = operational_builder


def _set_debug_provider(self, provider: Callable[[], str] | None) -> None:
    self._display_f3_debug_provider = provider


def _debug_current_text(self) -> str:
    provider = getattr(self, "_display_f3_debug_provider", None)
    if not callable(provider):
        return "DEBUG TÉCNICO F3\n\nAguardando primeiro ciclo da câmera."
    try:
        return str(provider())
    except Exception as exc:
        return f"DEBUG TÉCNICO F3\n\nerro={type(exc).__name__}: {exc}"


def _install_debug_window() -> None:
    cls = DisplayProductionF3Window
    original_init = cls.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._display_f3_debug_provider = None
        self._display_f3_debug_window = None
        self._display_f3_debug_text_widget = None
        self._display_f3_debug_copy_status = None

        button = tk.Button(
            self.project_frame,
            text="DEBUG TÉCNICO",
            command=self.open_technical_debug,
            font=("DejaVu Sans", 8, "bold"),
            bg="#1E293B",
            fg="#E2E8F0",
            activebackground="#334155",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        button.grid(
            row=0,
            column=2,
            rowspan=2,
            sticky="e",
            padx=(0, 10),
            pady=7,
        )
        self.technical_debug_button = button

    def refresh_debug(self):
        widget = getattr(self, "_display_f3_debug_text_widget", None)
        if widget is None:
            return
        text = _debug_current_text(self)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def copy_debug(self):
        text = _debug_current_text(self)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            status = getattr(self, "_display_f3_debug_copy_status", None)
            if status is not None:
                status.configure(text="DEBUG COPIADO PARA A ÁREA DE TRANSFERÊNCIA")
                status.after(1800, lambda: status.configure(text=""))
        except Exception:
            return

    def close_debug(self):
        top = getattr(self, "_display_f3_debug_window", None)
        self._display_f3_debug_window = None
        self._display_f3_debug_text_widget = None
        self._display_f3_debug_copy_status = None
        if top is not None:
            try:
                top.destroy()
            except Exception:
                pass

    def open_debug(self):
        existing = getattr(self, "_display_f3_debug_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    self.refresh_technical_debug()
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        top = tk.Toplevel(self.root)
        self._display_f3_debug_window = top
        top.title("ODIN • DISPLAY F3 • DEBUG TÉCNICO")
        top.configure(bg=DEBUG_BG)
        top.geometry("980x640")
        top.minsize(760, 480)
        try:
            top.transient(self.root)
        except Exception:
            pass
        top.grid_rowconfigure(1, weight=1)
        top.grid_columnconfigure(0, weight=1)

        header = tk.Frame(top, bg=DEBUG_BG)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        tk.Label(
            header,
            text="DEBUG TÉCNICO • DISPLAY F3",
            font=("DejaVu Sans", 14, "bold"),
            bg=DEBUG_BG,
            fg="#FFFFFF",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Copie o bloco completo e cole na conversa/chamado técnico.",
            font=("DejaVu Sans", 9),
            bg=DEBUG_BG,
            fg=DEBUG_MUTED,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        text_frame = tk.Frame(
            top,
            bg=DEBUG_PANEL,
            highlightbackground=DEBUG_BORDER,
            highlightthickness=1,
        )
        text_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        text_widget = tk.Text(
            text_frame,
            wrap="none",
            font=("DejaVu Sans Mono", 9),
            bg=DEBUG_PANEL,
            fg=DEBUG_TEXT,
            insertbackground="#FFFFFF",
            selectbackground="#1D4ED8",
            selectforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
        )
        scroll_y = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        scroll_x = tk.Scrollbar(text_frame, orient="horizontal", command=text_widget.xview)
        text_widget.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        text_widget.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self._display_f3_debug_text_widget = text_widget

        actions = tk.Frame(top, bg=DEBUG_BG)
        actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        actions.grid_columnconfigure(3, weight=1)

        for column, (label, command) in enumerate(
            (
                ("ATUALIZAR", self.refresh_technical_debug),
                ("COPIAR TUDO", self.copy_technical_debug),
                ("FECHAR", self.close_technical_debug),
            )
        ):
            tk.Button(
                actions,
                text=label,
                command=command,
                font=("DejaVu Sans", 9, "bold"),
                bg=DEBUG_ACTION if column < 2 else "#1E293B",
                fg="#FFFFFF",
                activebackground=DEBUG_ACTION_ACTIVE if column < 2 else "#334155",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                padx=14,
                pady=7,
                cursor="hand2",
            ).grid(row=0, column=column, padx=(0, 8))

        status = tk.Label(
            actions,
            text="",
            font=("DejaVu Sans", 8, "bold"),
            bg=DEBUG_BG,
            fg="#7DD3FC",
            anchor="e",
        )
        status.grid(row=0, column=3, sticky="e")
        self._display_f3_debug_copy_status = status

        top.protocol("WM_DELETE_WINDOW", self.close_technical_debug)
        top.bind("<Escape>", lambda _event: (self.close_technical_debug(), "break")[1])
        self.refresh_technical_debug()
        top.focus_force()

    cls.set_technical_debug_provider = _set_debug_provider
    cls.open_technical_debug = open_debug
    cls.refresh_technical_debug = refresh_debug
    cls.copy_technical_debug = copy_debug
    cls.close_technical_debug = close_debug
    cls.__init__ = init


def _install_debug_runtime_provider() -> None:
    cls = auto_runtime_module.DisplayAutomaticCheckF3Mixin
    original_process = cls._process_display_auto_check

    def process(self):
        result = original_process(self)
        window = getattr(self, "display_f3_window", None)
        if window is not None:
            try:
                window.set_technical_debug_provider(
                    lambda owner=self: montar_debug_tecnico_display_f3(owner)
                )
            except Exception:
                pass
        return result

    cls._process_display_auto_check = process


_INSTALLED = False


def instalar_correcao_unknown_e_debug_display_f3() -> None:
    """Resolve UNKNOWN/OFF e instala painel copiável sem tocar na Produção F2."""
    global _INSTALLED
    if _INSTALLED:
        return
    _install_unknown_off_builder()
    _install_debug_window()
    _install_debug_runtime_provider()
    _INSTALLED = True
