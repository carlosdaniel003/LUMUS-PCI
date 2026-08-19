from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


DISPLAY_PROJECT_CONFIG_FILE = Path("data/config/odin_display_projects.json")
DISPLAY_PROJECT_SCHEMA_VERSION = 1


def normalizar_nome_projeto_display(nome: str | None) -> str:
    texto = re.sub(r"\s+", " ", str(nome or "").strip())
    return texto.upper()


def normalizar_resolucao_display(valor) -> tuple[int, int] | None:
    largura = altura = None
    if isinstance(valor, dict):
        largura = valor.get("width", valor.get("largura"))
        altura = valor.get("height", valor.get("altura"))
    elif isinstance(valor, (list, tuple)) and len(valor) >= 2:
        largura, altura = valor[0], valor[1]
    elif isinstance(valor, str):
        match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", valor)
        if match:
            largura, altura = match.group(1), match.group(2)

    try:
        largura = int(largura)
        altura = int(altura)
    except (TypeError, ValueError):
        return None

    if largura < 1 or altura < 1:
        return None
    return largura, altura


def _resolucao_dict(resolucao: tuple[int, int] | None) -> dict | None:
    if resolucao is None:
        return None
    return {"width": int(resolucao[0]), "height": int(resolucao[1])}


def normalizar_mascara_display(mascara: dict, indice: int = 1) -> dict | None:
    if not isinstance(mascara, dict):
        return None

    tipo = str(mascara.get("type", mascara.get("tipo", ""))).strip().lower()
    identificador = str(mascara.get("id") or f"MASK_{indice:03d}").strip()
    if not identificador:
        identificador = f"MASK_{indice:03d}"

    try:
        if tipo == "rectangle":
            x = int(mascara.get("x"))
            y = int(mascara.get("y"))
            width = int(mascara.get("width"))
            height = int(mascara.get("height"))
            if width < 1 or height < 1:
                return None
            return {
                "id": identificador,
                "type": "rectangle",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            }

        if tipo == "circle":
            cx = int(mascara.get("cx"))
            cy = int(mascara.get("cy"))
            radius = int(mascara.get("radius"))
            if radius < 1:
                return None
            return {
                "id": identificador,
                "type": "circle",
                "cx": cx,
                "cy": cy,
                "radius": radius,
            }

        if tipo == "polygon":
            pontos_origem = mascara.get("points", [])
            if not isinstance(pontos_origem, (list, tuple)):
                return None
            pontos: list[list[int]] = []
            for ponto in pontos_origem:
                if not isinstance(ponto, (list, tuple)) or len(ponto) < 2:
                    return None
                pontos.append([int(ponto[0]), int(ponto[1])])
            if len(pontos) < 3:
                return None
            return {
                "id": identificador,
                "type": "polygon",
                "points": pontos,
            }
    except (TypeError, ValueError):
        return None

    return None


def normalizar_mascaras_display(mascaras) -> list[dict]:
    if not isinstance(mascaras, (list, tuple)):
        return []
    resultado: list[dict] = []
    ids_usados: set[str] = set()
    for indice, mascara in enumerate(mascaras, start=1):
        normalizada = normalizar_mascara_display(mascara, indice)
        if normalizada is None:
            continue
        identificador = normalizada["id"]
        if identificador in ids_usados:
            identificador = f"MASK_{indice:03d}"
            normalizada["id"] = identificador
        ids_usados.add(identificador)
        resultado.append(normalizada)
    return resultado


class DisplayProjectRepository:
    """Persistência exclusiva do F3.

    Este repositório não usa ConfigRepository, ``led_projects`` ou qualquer
    estado do modo F2. O arquivo próprio permite evoluir o Display sem alterar
    o schema da inspeção PCI LED.
    """

    def __init__(self, config_file: str | Path | None = None) -> None:
        self.config_file = Path(config_file or DISPLAY_PROJECT_CONFIG_FILE)

    @staticmethod
    def _estrutura_vazia() -> dict:
        return {
            "schema_version": DISPLAY_PROJECT_SCHEMA_VERSION,
            "active_project": "",
            "project_order": [],
            "projects": {},
        }

    def _carregar(self) -> dict:
        if not self.config_file.exists():
            return self._estrutura_vazia()
        try:
            with open(self.config_file, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return self._estrutura_vazia()
        return self._normalizar_estrutura(dados)

    def _normalizar_estrutura(self, dados) -> dict:
        if not isinstance(dados, dict):
            dados = {}
        projetos_origem = dados.get("projects", {})
        projetos: dict[str, dict] = {}
        if isinstance(projetos_origem, dict):
            for chave, projeto in projetos_origem.items():
                if not isinstance(projeto, dict):
                    continue
                nome = normalizar_nome_projeto_display(projeto.get("name", chave))
                if not nome:
                    continue
                resolucao = normalizar_resolucao_display(
                    projeto.get("master_resolution")
                )
                projetos[nome] = {
                    "name": nome,
                    "master_resolution": _resolucao_dict(resolucao),
                    "masks": normalizar_mascaras_display(projeto.get("masks", [])),
                    "updated_at": projeto.get("updated_at"),
                }

        ordem: list[str] = []
        ordem_origem = dados.get("project_order", [])
        if isinstance(ordem_origem, list):
            for item in ordem_origem:
                nome = normalizar_nome_projeto_display(item)
                if nome in projetos and nome not in ordem:
                    ordem.append(nome)
        for nome in projetos:
            if nome not in ordem:
                ordem.append(nome)

        ativo = normalizar_nome_projeto_display(dados.get("active_project"))
        if ativo not in projetos:
            ativo = ordem[0] if ordem else ""

        return {
            "schema_version": DISPLAY_PROJECT_SCHEMA_VERSION,
            "active_project": ativo,
            "project_order": ordem,
            "projects": projetos,
        }

    def _escrever(self, dados: dict) -> None:
        normalizados = self._normalizar_estrutura(dados)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.config_file.with_suffix(self.config_file.suffix + ".tmp")
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(normalizados, arquivo, indent=4, ensure_ascii=False)
            arquivo.flush()
        temporario.replace(self.config_file)

    def listar_projetos(self) -> list[str]:
        return list(self._carregar()["project_order"])

    def obter_projeto_ativo(self) -> str:
        return str(self._carregar()["active_project"])

    def carregar_projeto(self, nome: str | None = None) -> dict | None:
        dados = self._carregar()
        nome_normalizado = normalizar_nome_projeto_display(nome)
        if not nome_normalizado:
            nome_normalizado = dados["active_project"]
        projeto = dados["projects"].get(nome_normalizado)
        return deepcopy(projeto) if projeto is not None else None

    def adicionar_projeto(
        self,
        nome: str,
        resolucao_mestra=None,
    ) -> bool:
        nome_normalizado = normalizar_nome_projeto_display(nome)
        if not nome_normalizado:
            return False
        dados = self._carregar()
        if nome_normalizado in dados["projects"]:
            return False
        resolucao = normalizar_resolucao_display(resolucao_mestra)
        dados["projects"][nome_normalizado] = {
            "name": nome_normalizado,
            "master_resolution": _resolucao_dict(resolucao),
            "masks": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        dados["project_order"].append(nome_normalizado)
        if not dados["active_project"]:
            dados["active_project"] = nome_normalizado
        self._escrever(dados)
        return True

    def definir_projeto_ativo(self, nome: str) -> bool:
        nome_normalizado = normalizar_nome_projeto_display(nome)
        dados = self._carregar()
        if nome_normalizado not in dados["projects"]:
            return False
        dados["active_project"] = nome_normalizado
        self._escrever(dados)
        return True

    def renomear_projeto(self, nome_atual: str, novo_nome: str) -> bool:
        atual = normalizar_nome_projeto_display(nome_atual)
        novo = normalizar_nome_projeto_display(novo_nome)
        dados = self._carregar()
        if not atual or not novo or atual not in dados["projects"]:
            return False
        if novo != atual and novo in dados["projects"]:
            return False
        if novo == atual:
            return True
        projeto = dados["projects"].pop(atual)
        projeto["name"] = novo
        projeto["updated_at"] = datetime.now(timezone.utc).isoformat()
        dados["projects"][novo] = projeto
        dados["project_order"] = [novo if item == atual else item for item in dados["project_order"]]
        if dados["active_project"] == atual:
            dados["active_project"] = novo
        self._escrever(dados)
        return True

    def remover_projeto(self, nome: str) -> bool:
        nome_normalizado = normalizar_nome_projeto_display(nome)
        dados = self._carregar()
        if nome_normalizado not in dados["projects"]:
            return False
        dados["projects"].pop(nome_normalizado)
        dados["project_order"] = [
            item for item in dados["project_order"] if item != nome_normalizado
        ]
        if dados["active_project"] == nome_normalizado:
            dados["active_project"] = (
                dados["project_order"][0] if dados["project_order"] else ""
            )
        self._escrever(dados)
        return True

    def salvar_resolucao_mestra(self, nome: str, largura: int, altura: int) -> bool:
        projeto = self.carregar_projeto(nome)
        resolucao = normalizar_resolucao_display((largura, altura))
        if projeto is None or resolucao is None:
            return False
        return self.salvar_configuracao_projeto(
            nome,
            resolucao,
            projeto.get("masks", []),
        )

    def salvar_mascaras(self, nome: str, mascaras) -> bool:
        projeto = self.carregar_projeto(nome)
        if projeto is None:
            return False
        resolucao = normalizar_resolucao_display(
            projeto.get("master_resolution")
        )
        if resolucao is None:
            return False
        return self.salvar_configuracao_projeto(nome, resolucao, mascaras)

    def salvar_configuracao_projeto(
        self,
        nome: str,
        resolucao_mestra,
        mascaras,
    ) -> bool:
        nome_normalizado = normalizar_nome_projeto_display(nome)
        resolucao = normalizar_resolucao_display(resolucao_mestra)
        if not nome_normalizado or resolucao is None:
            return False
        dados = self._carregar()
        if nome_normalizado not in dados["projects"]:
            return False
        dados["projects"][nome_normalizado] = {
            "name": nome_normalizado,
            "master_resolution": _resolucao_dict(resolucao),
            "masks": normalizar_mascaras_display(mascaras),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        dados["active_project"] = nome_normalizado
        self._escrever(dados)
        return True
