from __future__ import annotations

"""Memória física genérica do último CHECK confirmado no Display F3.

O sequenciador lógico e o status físico são coisas diferentes. Depois que um
CHECK é aprovado, o próximo CHECK lógico pode mudar imediatamente enquanto a
placa física continua, por alguns frames, no estado anterior. A comparação da
cena inteira também pode preferir falsamente a referência PLACA DESLIGADA porque
quase todos os pixels da placa permanecem iguais.

Esta camada corrige SOMENTE a apresentação do estado físico. Ela guarda o último
CHECK realmente aprovado e, quando o classificador global retorna OFF/UNKNOWN,
confirma no frame atual se as máscaras que deveriam estar ACESAS ainda se parecem
mais com a foto daquele CHECK do que com a referência de placa desligada.

Nenhum campo de decisão (kind/allow_auto/gates) é alterado. Portanto esta memória
não aprova, reprova nem avança CHECKs. Funciona para qualquer CHECK cadastrado,
sem nomes especiais como H1/BLUE/USB/AUX/CHECK_005.
"""

from copy import deepcopy
from math import ceil

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_physical_learning_policy as physical_policy_module
from src.platform.display_production_f3 import DisplayProductionF3Mixin


F3_PHYSICAL_STATUS_MEMORY_SOURCE = "f3_last_confirmed_check_physical_status"
F3_PHYSICAL_STATUS_POWER_RATIO = 0.60


def _event_type(event: dict | None) -> str:
    if not isinstance(event, dict):
        return ""
    return str(event.get("event") or "").strip()


def _current_context(app) -> dict | None:
    try:
        context = app._display_auto_current_context()
    except Exception:
        return None
    return context if isinstance(context, dict) else None


def limpar_memoria_status_fisico_f3(app, reason: str = "") -> None:
    app._display_f3_physical_status_memory_project = ""
    app._display_f3_physical_status_memory_check_id = ""
    app._display_f3_physical_status_memory_check_name = ""
    app._display_f3_physical_status_memory_reason = str(reason or "")


def lembrar_check_fisico_confirmado_f3(app, context: dict | None) -> bool:
    if not isinstance(context, dict):
        return False
    project_name = str(context.get("project_name") or "").strip()
    check_id = str(context.get("check_id") or "").strip()
    check_name = str(context.get("check_name") or check_id).strip().upper()
    if not project_name or not check_id:
        return False

    app._display_f3_physical_status_memory_project = project_name
    app._display_f3_physical_status_memory_check_id = check_id
    app._display_f3_physical_status_memory_check_name = check_name or check_id.upper()
    app._display_f3_physical_status_memory_reason = "check_aprovado"
    return True


def _memoria_do_projeto(app, project_name: str) -> tuple[str, str] | None:
    remembered_project = str(
        getattr(app, "_display_f3_physical_status_memory_project", "") or ""
    ).strip()
    check_id = str(
        getattr(app, "_display_f3_physical_status_memory_check_id", "") or ""
    ).strip()
    check_name = str(
        getattr(app, "_display_f3_physical_status_memory_check_name", "") or check_id
    ).strip().upper()
    if not remembered_project or remembered_project != str(project_name or "").strip():
        return None
    if not check_id:
        return None
    return check_id, (check_name or check_id.upper())


def evidencia_confirma_check_ainda_ligado_f3(evidence: dict | None) -> bool:
    if not isinstance(evidence, dict) or not bool(evidence.get("available")):
        return False
    try:
        valid = max(0, int(evidence.get("valid_votes", 0) or 0))
        powered = max(0, int(evidence.get("powered_votes", 0) or 0))
        off_votes = max(0, int(evidence.get("off_votes", 0) or 0))
    except (TypeError, ValueError):
        return False
    if valid <= 0:
        return False

    required = max(1, int(ceil(valid * F3_PHYSICAL_STATUS_POWER_RATIO)))
    return bool(powered >= required and powered > off_votes)


def aplicar_memoria_status_fisico_f3(
    app,
    state: dict | None,
    frame,
    project_name: str,
) -> dict:
    """Corrige texto/cor de falso OFF sem mudar qualquer autoridade de decisão."""
    result = deepcopy(state) if isinstance(state, dict) else {}
    kind = str(result.get("kind") or "unknown").strip().lower()

    if kind == "empty":
        limpar_memoria_status_fisico_f3(app, "suporte_vazio")
        return result

    # Se o classificador já reconheceu um CHECK ligado, não há nada para corrigir.
    if kind == "check":
        return result

    if kind not in {"off", "unknown"}:
        return result

    remembered = _memoria_do_projeto(app, project_name)
    if remembered is None:
        return result
    check_id, check_name = remembered

    repository = getattr(app, "display_project_repository", None)
    matcher = getattr(app, "_display_f3_operational_matcher", None)
    if repository is None or matcher is None:
        return result

    try:
        evidence = physical_policy_module.avaliar_evidencia_energia_check_pelas_mascaras_f3(
            repository=repository,
            matcher=matcher,
            frame=frame,
            project_name=str(project_name),
            check_id=check_id,
        )
    except Exception:
        return result

    result["physical_status_memory_evidence"] = evidence
    if not evidencia_confirma_check_ainda_ligado_f3(evidence):
        return result

    # Deliberadamente NÃO alteramos kind, allow_auto, check_id operacional,
    # F3_DECISION_ALLOWED_KEY ou qualquer outro gate. É apenas verdade visual.
    result["text"] = f"PLACA NO SUPORTE • LIGADA • DISPLAY EM {check_name}"
    result["color"] = operational_module.F3_OPERATIONAL_STATUS_COLORS["check"]
    result["physical_status_memory_override"] = True
    result["physical_status_memory_underlying_kind"] = kind
    result["physical_status_memory_check_id"] = check_id
    result["physical_status_memory_check_name"] = check_name
    result["physical_status_memory_source"] = F3_PHYSICAL_STATUS_MEMORY_SOURCE
    return result


def _install_operational_status_memory() -> None:
    if bool(
        getattr(
            operational_module,
            "_display_f3_physical_status_memory_installed",
            False,
        )
    ):
        return

    previous_builder = operational_module._build_operational_state

    def build(self, frame, project_name: str, context: dict | None):
        state = previous_builder(self, frame, project_name, context)
        return aplicar_memoria_status_fisico_f3(
            self,
            state,
            frame,
            project_name,
        )

    operational_module._build_operational_state = build
    operational_module._display_f3_physical_status_memory_installed = True


def _install_confirmed_check_memory() -> None:
    cls = DisplayProductionF3Mixin
    if bool(getattr(cls, "_display_f3_physical_status_register_installed", False)):
        return

    previous_register = cls.registrar_resultado_check_display_f3

    def register(self, aprovado: bool = True):
        context_before = _current_context(self)
        event = previous_register(self, aprovado)
        event_type = _event_type(event)

        # Genérico: qualquer CHECK aprovado passa a ser a verdade física mais
        # recente. No evento plate_ok, context_before ainda é o último CHECK.
        if bool(aprovado) and event_type in {"check_advanced", "plate_ok"}:
            lembrar_check_fisico_confirmado_f3(self, context_before)
        return event

    cls.registrar_resultado_check_display_f3 = register
    cls._display_f3_physical_status_register_installed = True


def _install_session_lifecycle() -> None:
    cls = DisplayProductionF3Mixin
    if bool(getattr(cls, "_display_f3_physical_status_session_installed", False)):
        return

    previous_activate = cls._ativar_tela_producao_display_f3
    previous_close = cls.fechar_tela_producao_display_f3

    def activate(self):
        limpar_memoria_status_fisico_f3(self, "nova_sessao_f3")
        return previous_activate(self)

    def close(self):
        limpar_memoria_status_fisico_f3(self, "f3_fechado")
        return previous_close(self)

    cls._ativar_tela_producao_display_f3 = activate
    cls.fechar_tela_producao_display_f3 = close
    cls._display_f3_physical_status_session_installed = True


_INSTALLED = False


def instalar_memoria_status_fisico_display_f3() -> None:
    """Instala a última camada de status físico, isolada do F2 e do sequenciador."""
    global _INSTALLED
    if _INSTALLED:
        return
    _install_operational_status_memory()
    _install_confirmed_check_memory()
    _install_session_lifecycle()
    _INSTALLED = True
