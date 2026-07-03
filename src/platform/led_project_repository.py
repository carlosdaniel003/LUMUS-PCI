from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from config import (
    DEFAULT_SAVE_ANALYSIS_RESULTS,
    DEFAULT_THRESHOLD_V,
)
from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection


_PATCH_INSTALADO = False


def normalizar_nome_projeto_led(nome: str | None) -> str:
    texto = re.sub(r"\s+", " ", str(nome or "").strip())
    return texto.upper()


def _estrutura_base_configuracao() -> dict:
    return {
        "project": "ODIN",
        "version": "0.13.0",
        "inspection_method": (
            "single_selected_led_reference_classifier_modular"
        ),
        "threshold_v": DEFAULT_THRESHOLD_V,
    }


def _obter_settings(configuracao: dict) -> dict:
    settings = configuracao.get("settings", {})
    if not isinstance(settings, dict):
        settings = {}

    settings.setdefault(
        "save_analysis_results",
        DEFAULT_SAVE_ANALYSIS_RESULTS,
    )
    settings["camera"] = ConfigRepository.normalizar_configuracoes_camera(
        settings.get("camera")
    )
    configuracao["settings"] = settings
    return settings


def _normalizar_projetos(configuracao: dict) -> dict:
    projetos_origem = configuracao.get("led_projects", {})
    projetos: dict[str, dict] = {}

    if isinstance(projetos_origem, dict):
        for chave, dados in projetos_origem.items():
            nome = normalizar_nome_projeto_led(
                dados.get("name", chave)
                if isinstance(dados, dict)
                else chave
            )
            if not nome or not isinstance(dados, dict):
                continue

            leds = dados.get("fixed_leds", [])
            if not isinstance(leds, list):
                leds = []

            projetos[nome] = {
                "name": nome,
                "fixed_leds": leds,
                "updated_at": dados.get("updated_at"),
            }

    leds_legados = configuracao.get("fixed_leds", [])
    if not projetos and isinstance(leds_legados, list) and leds_legados:
        projetos["PADRÃO"] = {
            "name": "PADRÃO",
            "fixed_leds": leds_legados,
            "updated_at": None,
        }

    configuracao["led_projects"] = projetos
    return projetos


def _normalizar_ordem_projetos(
    configuracao: dict,
    projetos: dict,
) -> list[str]:
    settings = _obter_settings(configuracao)
    ordem_origem = settings.get("led_project_order", [])
    ordem: list[str] = []

    if isinstance(ordem_origem, list):
        for item in ordem_origem:
            nome = normalizar_nome_projeto_led(item)
            if nome in projetos and nome not in ordem:
                ordem.append(nome)

    for nome in projetos.keys():
        if nome not in ordem:
            ordem.append(nome)

    settings["led_project_order"] = ordem
    return ordem


def _obter_projeto_ativo(configuracao: dict, projetos: dict) -> str:
    settings = _obter_settings(configuracao)
    nome = normalizar_nome_projeto_led(
        settings.get("active_led_project")
    )

    if nome in projetos:
        return nome

    ordem = _normalizar_ordem_projetos(configuracao, projetos)
    if ordem:
        nome = ordem[0]
        settings["active_led_project"] = nome
        return nome

    settings["active_led_project"] = ""
    return ""


def _sincronizar_espelho_ativo(
    configuracao: dict,
    projetos: dict,
) -> str:
    nome_ativo = _obter_projeto_ativo(configuracao, projetos)
    configuracao["fixed_leds"] = list(
        projetos.get(nome_ativo, {}).get("fixed_leds", [])
    )
    return nome_ativo


def _escrever_configuracao(
    repository: ConfigRepository,
    configuracao: dict,
) -> None:
    repository.config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(repository.config_file, "w", encoding="utf-8") as arquivo:
        json.dump(
            configuracao,
            arquivo,
            indent=4,
            ensure_ascii=False,
        )


def instalar_repositorio_projetos_led() -> None:
    global _PATCH_INSTALADO

    if _PATCH_INSTALADO:
        return

    def listar_projetos_led(self: ConfigRepository) -> list[str]:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        return list(_normalizar_ordem_projetos(configuracao, projetos))

    def obter_projeto_led_ativo(self: ConfigRepository) -> str:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        return _obter_projeto_ativo(configuracao, projetos)

    def definir_projeto_led_ativo(
        self: ConfigRepository,
        nome_projeto: str,
        criar: bool = False,
    ) -> bool:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        if not configuracao:
            configuracao = _estrutura_base_configuracao()

        projetos = _normalizar_projetos(configuracao)
        ordem = _normalizar_ordem_projetos(configuracao, projetos)
        nome = normalizar_nome_projeto_led(nome_projeto)
        if not nome:
            return False

        if nome not in projetos:
            if not criar:
                return False
            projetos[nome] = {
                "name": nome,
                "fixed_leds": [],
                "updated_at": None,
            }
            ordem.append(nome)

        settings = _obter_settings(configuracao)
        settings["active_led_project"] = nome
        settings["led_project_order"] = ordem
        configuracao["led_projects"] = projetos
        configuracao["fixed_leds"] = list(
            projetos[nome].get("fixed_leds", [])
        )
        _escrever_configuracao(self, configuracao)
        return True

    def adicionar_projeto_led(
        self: ConfigRepository,
        nome_projeto: str,
    ) -> bool:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        if not configuracao:
            configuracao = _estrutura_base_configuracao()

        projetos = _normalizar_projetos(configuracao)
        ordem = _normalizar_ordem_projetos(configuracao, projetos)
        nome = normalizar_nome_projeto_led(nome_projeto)
        if not nome or nome in projetos:
            return False

        projetos[nome] = {
            "name": nome,
            "fixed_leds": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        ordem.append(nome)
        settings = _obter_settings(configuracao)
        settings["led_project_order"] = ordem
        if not settings.get("active_led_project"):
            settings["active_led_project"] = nome

        configuracao["led_projects"] = projetos
        _sincronizar_espelho_ativo(configuracao, projetos)
        _escrever_configuracao(self, configuracao)
        return True

    def renomear_projeto_led(
        self: ConfigRepository,
        nome_atual: str,
        novo_nome: str,
    ) -> bool:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        ordem = _normalizar_ordem_projetos(configuracao, projetos)
        atual = normalizar_nome_projeto_led(nome_atual)
        novo = normalizar_nome_projeto_led(novo_nome)

        if (
            not atual
            or not novo
            or atual not in projetos
            or (novo != atual and novo in projetos)
        ):
            return False
        if novo == atual:
            return True

        dados = dict(projetos.pop(atual))
        dados["name"] = novo
        dados["updated_at"] = datetime.now(timezone.utc).isoformat()
        projetos[novo] = dados
        ordem = [novo if nome == atual else nome for nome in ordem]

        settings = _obter_settings(configuracao)
        if normalizar_nome_projeto_led(
            settings.get("active_led_project")
        ) == atual:
            settings["active_led_project"] = novo
        settings["led_project_order"] = ordem

        configuracao["led_projects"] = projetos
        _sincronizar_espelho_ativo(configuracao, projetos)
        _escrever_configuracao(self, configuracao)
        return True

    def remover_projeto_led(
        self: ConfigRepository,
        nome_projeto: str,
    ) -> bool:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        ordem = _normalizar_ordem_projetos(configuracao, projetos)
        nome = normalizar_nome_projeto_led(nome_projeto)
        if not nome or nome not in projetos:
            return False

        projetos.pop(nome)
        ordem = [item for item in ordem if item != nome]
        settings = _obter_settings(configuracao)
        ativo = normalizar_nome_projeto_led(
            settings.get("active_led_project")
        )
        if ativo == nome:
            settings["active_led_project"] = ordem[0] if ordem else ""
        settings["led_project_order"] = ordem

        configuracao["led_projects"] = projetos
        _sincronizar_espelho_ativo(configuracao, projetos)
        _escrever_configuracao(self, configuracao)
        return True

    def reordenar_projetos_led(
        self: ConfigRepository,
        nova_ordem: list[str],
    ) -> bool:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        ordem_normalizada: list[str] = []

        for item in nova_ordem:
            nome = normalizar_nome_projeto_led(item)
            if nome in projetos and nome not in ordem_normalizada:
                ordem_normalizada.append(nome)

        if set(ordem_normalizada) != set(projetos.keys()):
            return False

        settings = _obter_settings(configuracao)
        settings["led_project_order"] = ordem_normalizada
        configuracao["led_projects"] = projetos
        _escrever_configuracao(self, configuracao)
        return True

    def salvar_leds_fixos_por_projeto(
        self: ConfigRepository,
        leds_fixos: list[LedSelection],
        largura_base: int | None = None,
        altura_base: int | None = None,
        projeto: str | None = None,
    ) -> dict:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        if not configuracao:
            configuracao = _estrutura_base_configuracao()

        settings = _obter_settings(configuracao)
        projetos = _normalizar_projetos(configuracao)
        ordem = _normalizar_ordem_projetos(configuracao, projetos)
        nome = normalizar_nome_projeto_led(
            projeto or settings.get("active_led_project")
        )
        if not nome:
            nome = "PADRÃO"

        leds_para_salvar = []
        for led_fixo in leds_fixos:
            if largura_base and altura_base:
                leds_para_salvar.append(
                    led_fixo.com_normalizacao(
                        largura_base=largura_base,
                        altura_base=altura_base,
                    )
                )
            else:
                leds_para_salvar.append(led_fixo)

        dados_leds = [
            led_fixo.to_dict()
            for led_fixo in leds_para_salvar
        ]
        projetos[nome] = {
            "name": nome,
            "fixed_leds": dados_leds,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if nome not in ordem:
            ordem.append(nome)
        settings["active_led_project"] = nome
        settings["led_project_order"] = ordem
        configuracao["led_projects"] = projetos

        # Espelho mantido por compatibilidade com versões anteriores.
        configuracao["fixed_leds"] = dados_leds
        _escrever_configuracao(self, configuracao)
        return configuracao

    def carregar_leds_fixos_por_projeto(
        self: ConfigRepository,
        projeto: str | None = None,
    ) -> list[LedSelection]:
        configuracao = self.carregar_configuracao_existente_sem_alerta()
        projetos = _normalizar_projetos(configuracao)
        nome = normalizar_nome_projeto_led(projeto)

        if not nome:
            nome = _obter_projeto_ativo(configuracao, projetos)

        if nome and nome in projetos:
            dados_leds = projetos[nome].get("fixed_leds", [])
        else:
            dados_leds = configuracao.get("fixed_leds", [])

        if not isinstance(dados_leds, list):
            return []

        leds_fixos = []
        for dados_led_fixo in dados_leds:
            led_fixo = LedSelection.from_dict(dados_led_fixo)
            if led_fixo is not None:
                leds_fixos.append(led_fixo)
        return leds_fixos

    ConfigRepository.listar_projetos_led = listar_projetos_led
    ConfigRepository.obter_projeto_led_ativo = obter_projeto_led_ativo
    ConfigRepository.definir_projeto_led_ativo = definir_projeto_led_ativo
    ConfigRepository.adicionar_projeto_led = adicionar_projeto_led
    ConfigRepository.renomear_projeto_led = renomear_projeto_led
    ConfigRepository.remover_projeto_led = remover_projeto_led
    ConfigRepository.reordenar_projetos_led = reordenar_projetos_led
    ConfigRepository.salvar_leds_fixos = salvar_leds_fixos_por_projeto
    ConfigRepository.carregar_leds_fixos = carregar_leds_fixos_por_projeto
    _PATCH_INSTALADO = True
