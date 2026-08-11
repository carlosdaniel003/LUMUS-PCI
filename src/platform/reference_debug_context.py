from __future__ import annotations

from pathlib import Path


_TIPOS = (
    ("aceso", "ACESO", "features_referencia_acesa"),
    ("apagado", "APAGADO", "features_referencia_apagada"),
    ("pouca_luz", "POUCA LUZ", "features_referencia_pouca_luz"),
)

_FEATURES_RESUMO = (
    "v_mean",
    "v_max",
    "v_std",
    "s_mean",
    "h_mean",
    "glow_score",
    "percent_hot_250",
)


def _valor_feature(features, nome: str):
    if features is None:
        return None
    try:
        return getattr(features, nome)
    except Exception:
        return None


def _resumo_features_objeto(features) -> dict:
    if features is None:
        return {}
    return {
        nome: _valor_feature(features, nome)
        for nome in _FEATURES_RESUMO
    }


def _resumo_features_dict(features) -> dict:
    if not isinstance(features, dict):
        return {}
    return {
        nome: features.get(nome)
        for nome in _FEATURES_RESUMO
        if nome in features
    }


def _resumo_roi(roi) -> dict:
    if not isinstance(roi, dict):
        return {}

    tipo = str(roi.get("tipo_roi") or "circulo")
    resumo = {
        "tipo": tipo,
        "centro_x": roi.get("centro_x"),
        "centro_y": roi.get("centro_y"),
    }
    if tipo.lower() == "segmento":
        resumo.update(
            {
                "largura": roi.get("largura"),
                "altura": roi.get("altura"),
                "angulo": roi.get("angulo"),
            }
        )
    else:
        resumo["raio"] = roi.get("raio")
    return resumo


def criar_contexto_debug_referencias(app) -> dict:
    """Extrai somente dados diagnósticos das referências ativas do projeto."""
    projeto = ""
    obter_projeto = getattr(app, "_projeto_referencia_ativo", None)
    if callable(obter_projeto):
        try:
            projeto = str(obter_projeto() or "").strip()
        except Exception:
            projeto = ""
    if not projeto:
        projeto = str(getattr(app, "projeto_led_ativo", "") or "").strip()

    grupos_origem = getattr(app, "_referencias_ativas_por_tipo", {})
    if not isinstance(grupos_origem, dict):
        grupos_origem = {}

    grupos = {}
    for chave, titulo, atributo_agregado in _TIPOS:
        entradas = list(grupos_origem.get(chave, []) or ())
        amostras = []
        globais = 0
        projeto_qtd = 0

        for posicao, entrada in enumerate(entradas, start=1):
            if not isinstance(entrada, dict):
                continue
            scope = "global" if entrada.get("scope") == "global" else "project"
            if scope == "global":
                globais += 1
            else:
                projeto_qtd += 1

            sample = entrada.get("sample", {})
            if not isinstance(sample, dict):
                sample = {}
            caminho = str(sample.get("image_path") or "")
            amostras.append(
                {
                    "numero": posicao,
                    "scope": scope,
                    "id": str(sample.get("id") or ""),
                    "arquivo": Path(caminho).name if caminho else "",
                    "roi": _resumo_roi(sample.get("roi")),
                    "features": _resumo_features_dict(sample.get("features")),
                }
            )

        grupos[chave] = {
            "titulo": titulo,
            "total": len(amostras),
            "globais": globais,
            "projeto": projeto_qtd,
            "amostras": amostras,
            "agregado": _resumo_features_objeto(
                getattr(app, atributo_agregado, None)
            ),
        }

    return {
        "projeto": projeto or "SEM PROJETO",
        "limite_por_estado": 3,
        "grupos": grupos,
        "classificacao": (
            "ACESO/APAGADO usam o perfil agregado das referências ativas; "
            "POUCA_LUZ permanece no diagnóstico óptico calibrado."
        ),
    }
