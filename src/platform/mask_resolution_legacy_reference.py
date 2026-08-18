from __future__ import annotations

from src.platform.fixed_mask_geometry_guard import (
    FixedMaskGeometryGuardMixin,
    copiar_mascaras_absolutas,
)


_PATCH_INSTALADO = False


def _resolucao_configurada(app) -> tuple[int, int] | None:
    configuracoes = getattr(app, "configuracoes_camera", None)
    if not isinstance(configuracoes, dict):
        return None
    try:
        largura = int(configuracoes.get("width", 0) or 0)
        altura = int(configuracoes.get("height", 0) or 0)
    except (TypeError, ValueError):
        return None
    if largura <= 0 or altura <= 0:
        return None
    return largura, altura


def _resolucao_referencia_legado(app, mascaras) -> tuple[int, int] | None:
    # Metadados explícitos do próprio LED sempre vencem qualquer inferência.
    for led in mascaras or ():
        largura = int(getattr(led, "largura_base", 0) or 0)
        altura = int(getattr(led, "altura_base", 0) or 0)
        if largura > 0 and altura > 0:
            return largura, altura

    ativa = getattr(app, "_mask_resolution_active", None)
    if ativa and len(ativa) == 2:
        try:
            largura, altura = int(ativa[0]), int(ativa[1])
        except (TypeError, ValueError):
            largura, altura = 0, 0
        if largura > 0 and altura > 0:
            return largura, altura

    configurada = _resolucao_configurada(app)
    if configurada is not None:
        return configurada

    obter_atual = getattr(app, "_mask_guard_current_resolution", None)
    if callable(obter_atual):
        try:
            return obter_atual()
        except Exception:
            return None
    return None


def instalar_referencia_resolucao_mascaras_legadas() -> None:
    """Faz máscaras legadas herdarem a base correta antes do primeiro frame."""
    global _PATCH_INSTALADO
    if _PATCH_INSTALADO:
        return

    def captura_com_referencia_legado(
        self,
        force: bool = False,
        source=None,
        project: str | None = None,
    ) -> None:
        with self._mask_guard_lock:
            projeto = str(project or self._mask_guard_active_project())
            if not force and projeto == self._mask_guard_project:
                return

            mascaras = (
                copiar_mascaras_absolutas(source)
                if source is not None
                else self._mask_guard_read_repository()
            )
            referencia = _resolucao_referencia_legado(self, mascaras)
            canonical = self._mask_guard_canonicalize(
                mascaras,
                referencia,
            )
            self._mask_guard_project = projeto
            self._mask_guard_snapshot = tuple(canonical)

    FixedMaskGeometryGuardMixin._mask_guard_capture = captura_com_referencia_legado
    FixedMaskGeometryGuardMixin._odin_legacy_resolution_reference_installed = True
    _PATCH_INSTALADO = True
