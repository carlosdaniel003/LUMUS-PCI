from __future__ import annotations

import copy
import json
from pathlib import Path
from uuid import uuid4

from src.platform.led_project_repository import normalizar_nome_projeto_led


MAX_REFERENCIAS_POR_ESTADO = 3
TIPOS_REFERENCIA = ("on", "off", "low_light")
CHAVES_LEGADAS = {
    "on": "reference_on",
    "off": "reference_off",
    "low_light": "reference_low_light",
}


class LimiteReferenciasError(ValueError):
    pass


def _amostra_valida(amostra) -> bool:
    if not isinstance(amostra, dict):
        return False
    return bool(amostra.get("image_path") or amostra.get("features"))


def normalizar_amostra(amostra: dict | None) -> dict | None:
    if not _amostra_valida(amostra):
        return None
    dados = copy.deepcopy(amostra)
    dados["id"] = str(dados.get("id") or uuid4().hex)
    features = dados.get("features", {})
    dados["features"] = copy.deepcopy(features) if isinstance(features, dict) else {}
    roi = dados.get("roi")
    if not isinstance(roi, dict):
        dados.pop("roi", None)
    dados["image_path"] = str(dados.get("image_path") or "")
    return dados


def _normalizar_grupo(grupo) -> dict[str, list[dict]]:
    origem = grupo if isinstance(grupo, dict) else {}
    saida: dict[str, list[dict]] = {}
    for tipo in TIPOS_REFERENCIA:
        itens = origem.get(tipo, [])
        if not isinstance(itens, list):
            itens = []
        normalizados = []
        for item in itens:
            amostra = normalizar_amostra(item)
            if amostra is not None:
                normalizados.append(amostra)
            if len(normalizados) >= MAX_REFERENCIAS_POR_ESTADO:
                break
        saida[tipo] = normalizados
    return saida


def normalizar_biblioteca_referencias(configuracao: dict | None) -> tuple[dict, bool]:
    dados = copy.deepcopy(configuracao) if isinstance(configuracao, dict) else {}
    alterado = False

    biblioteca = dados.get("reference_sets")
    migrar_legado = not isinstance(biblioteca, dict)
    if migrar_legado:
        biblioteca = {"version": 1, "global": {}}
        alterado = True
    else:
        biblioteca = copy.deepcopy(biblioteca)
        biblioteca["version"] = 1

    global_normalizado = _normalizar_grupo(biblioteca.get("global"))
    if migrar_legado:
        for tipo, chave in CHAVES_LEGADAS.items():
            amostra = normalizar_amostra(dados.get(chave))
            if amostra is not None and not global_normalizado[tipo]:
                global_normalizado[tipo].append(amostra)

    if biblioteca.get("global") != global_normalizado:
        alterado = True
    biblioteca["global"] = global_normalizado
    dados["reference_sets"] = biblioteca

    projetos = dados.get("led_projects", {})
    if isinstance(projetos, dict):
        novos_projetos = copy.deepcopy(projetos)
        for chave, projeto in list(novos_projetos.items()):
            if not isinstance(projeto, dict):
                continue
            refs = _normalizar_grupo(projeto.get("references"))
            if projeto.get("references") != refs:
                projeto["references"] = refs
                alterado = True
            novos_projetos[chave] = projeto
        dados["led_projects"] = novos_projetos

    return dados, alterado


def _grupo_projeto(configuracao: dict, projeto: str, criar: bool = False) -> dict[str, list[dict]]:
    nome = normalizar_nome_projeto_led(projeto)
    if not nome:
        return _normalizar_grupo({})

    projetos = configuracao.setdefault("led_projects", {})
    if not isinstance(projetos, dict):
        projetos = {}
        configuracao["led_projects"] = projetos

    dados_projeto = projetos.get(nome)
    if not isinstance(dados_projeto, dict):
        if not criar:
            return _normalizar_grupo({})
        dados_projeto = {
            "name": nome,
            "fixed_leds": [],
            "updated_at": None,
        }
        projetos[nome] = dados_projeto

    refs = _normalizar_grupo(dados_projeto.get("references"))
    if criar:
        dados_projeto["references"] = refs
        projetos[nome] = dados_projeto
    return refs


def obter_referencias_ativas(
    configuracao: dict | None,
    projeto: str | None,
    tipo: str,
) -> list[dict]:
    if tipo not in TIPOS_REFERENCIA:
        return []
    dados, _ = normalizar_biblioteca_referencias(configuracao)
    globais = dados["reference_sets"]["global"][tipo]
    locais = _grupo_projeto(dados, projeto or "", criar=False)[tipo]

    saida = []
    for indice, amostra in enumerate(globais):
        saida.append({
            "scope": "global",
            "index": indice,
            "sample": copy.deepcopy(amostra),
        })
    for indice, amostra in enumerate(locais):
        if len(saida) >= MAX_REFERENCIAS_POR_ESTADO:
            break
        saida.append({
            "scope": "project",
            "index": indice,
            "sample": copy.deepcopy(amostra),
        })
    return saida


def _quantidade_local(configuracao: dict, projeto: str, tipo: str) -> int:
    return len(_grupo_projeto(configuracao, projeto, criar=False)[tipo])


def _validar_nova_global(configuracao: dict, tipo: str) -> None:
    globais = configuracao["reference_sets"]["global"][tipo]
    nova_qtd_global = len(globais) + 1
    if nova_qtd_global > MAX_REFERENCIAS_POR_ESTADO:
        raise LimiteReferenciasError(
            f"Já existem {MAX_REFERENCIAS_POR_ESTADO} referências globais para este estado."
        )

    projetos = configuracao.get("led_projects", {})
    if not isinstance(projetos, dict):
        return
    for nome, projeto in projetos.items():
        if not isinstance(projeto, dict):
            continue
        nome_normalizado = normalizar_nome_projeto_led(projeto.get("name", nome))
        locais = _quantidade_local(configuracao, nome_normalizado, tipo)
        if nova_qtd_global + locais > MAX_REFERENCIAS_POR_ESTADO:
            raise LimiteReferenciasError(
                "Esta referência global faria o projeto "
                f"{nome_normalizado} ultrapassar o limite de "
                f"{MAX_REFERENCIAS_POR_ESTADO} referências ativas."
            )


def _validar_nova_local(configuracao: dict, projeto: str, tipo: str) -> None:
    globais = len(configuracao["reference_sets"]["global"][tipo])
    locais = _quantidade_local(configuracao, projeto, tipo)
    if globais + locais + 1 > MAX_REFERENCIAS_POR_ESTADO:
        raise LimiteReferenciasError(
            f"O projeto {normalizar_nome_projeto_led(projeto) or 'SEM PROJETO'} já atingiu "
            f"o limite de {MAX_REFERENCIAS_POR_ESTADO} referências ativas para este estado."
        )


def salvar_amostra_referencia(
    configuracao: dict | None,
    projeto: str | None,
    tipo: str,
    amostra: dict,
    scope: str = "project",
    index: int | None = None,
) -> dict:
    if tipo not in TIPOS_REFERENCIA:
        raise ValueError("tipo de referência inválido")
    dados, _ = normalizar_biblioteca_referencias(configuracao)
    amostra_normalizada = normalizar_amostra(amostra)
    if amostra_normalizada is None:
        raise ValueError("amostra de referência inválida")

    scope = "global" if str(scope).lower() == "global" else "project"
    if scope == "global":
        grupo = dados["reference_sets"]["global"][tipo]
        if index is None:
            _validar_nova_global(dados, tipo)
            grupo.append(amostra_normalizada)
        else:
            indice = int(index)
            if indice < 0 or indice >= len(grupo):
                raise IndexError("referência global não encontrada")
            amostra_normalizada["id"] = str(
                grupo[indice].get("id") or amostra_normalizada["id"]
            )
            grupo[indice] = amostra_normalizada
    else:
        nome = normalizar_nome_projeto_led(projeto)
        if not nome:
            raise ValueError("selecione um projeto em Carregar LEDs antes de salvar referência")
        grupo = _grupo_projeto(dados, nome, criar=True)[tipo]
        # _grupo_projeto retorna uma cópia normalizada; reaplica ao projeto ao final.
        if index is None:
            _validar_nova_local(dados, nome, tipo)
            grupo.append(amostra_normalizada)
        else:
            indice = int(index)
            if indice < 0 or indice >= len(grupo):
                raise IndexError("referência do projeto não encontrada")
            amostra_normalizada["id"] = str(
                grupo[indice].get("id") or amostra_normalizada["id"]
            )
            grupo[indice] = amostra_normalizada
        dados["led_projects"][nome]["references"] = {
            **_normalizar_grupo(dados["led_projects"][nome].get("references")),
            tipo: grupo,
        }

    return dados


def remover_amostra_referencia(
    configuracao: dict | None,
    projeto: str | None,
    tipo: str,
    scope: str,
    index: int,
) -> tuple[dict, dict | None]:
    if tipo not in TIPOS_REFERENCIA:
        raise ValueError("tipo de referência inválido")
    dados, _ = normalizar_biblioteca_referencias(configuracao)
    scope = "global" if str(scope).lower() == "global" else "project"

    if scope == "global":
        grupo = dados["reference_sets"]["global"][tipo]
    else:
        nome = normalizar_nome_projeto_led(projeto)
        if not nome or nome not in dados.get("led_projects", {}):
            return dados, None
        grupo = _grupo_projeto(dados, nome, criar=True)[tipo]

    indice = int(index)
    if indice < 0 or indice >= len(grupo):
        return dados, None
    removida = grupo.pop(indice)

    if scope == "project":
        dados["led_projects"][nome]["references"] = {
            **_normalizar_grupo(dados["led_projects"][nome].get("references")),
            tipo: grupo,
        }
    return dados, removida


def mover_escopo_referencia(
    configuracao: dict | None,
    projeto: str | None,
    tipo: str,
    scope_atual: str,
    index: int,
) -> dict:
    dados, _ = normalizar_biblioteca_referencias(configuracao)
    origem = "global" if str(scope_atual).lower() == "global" else "project"
    destino = "project" if origem == "global" else "global"

    copia = copy.deepcopy(dados)
    copia, removida = remover_amostra_referencia(
        copia,
        projeto,
        tipo,
        origem,
        index,
    )
    if removida is None:
        raise IndexError("referência não encontrada")
    return salvar_amostra_referencia(
        copia,
        projeto,
        tipo,
        removida,
        scope=destino,
        index=None,
    )


def sincronizar_espelho_legado(
    configuracao: dict | None,
    projeto: str | None,
) -> dict:
    dados, _ = normalizar_biblioteca_referencias(configuracao)
    for tipo, chave in CHAVES_LEGADAS.items():
        ativas = obter_referencias_ativas(dados, projeto, tipo)
        dados[chave] = copy.deepcopy(ativas[0]["sample"]) if ativas else {}
    return dados


def escrever_configuracao(repository, configuracao: dict) -> dict:
    arquivo = Path(repository.config_file)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo, "w", encoding="utf-8") as destino:
        json.dump(configuracao, destino, indent=4, ensure_ascii=False)
    return configuracao
