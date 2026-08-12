from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from src.infra.config_repository import ConfigRepository
from src.platform.led_project_repository import normalizar_nome_projeto_led


CHAVE_PREVIEWS_PROJETO = "led_project_previews"
_PATCH_INSTALADO = False


def _obter_mapa_previews(configuracao: dict | None) -> dict:
    if not isinstance(configuracao, dict):
        return {}
    origem = configuracao.get(CHAVE_PREVIEWS_PROJETO, {})
    if not isinstance(origem, dict):
        return {}

    saida = {}
    for chave, dados in origem.items():
        nome = normalizar_nome_projeto_led(chave)
        if not nome or not isinstance(dados, dict):
            continue
        caminho = str(dados.get("image_path") or "").strip()
        if not caminho:
            continue
        saida[nome] = {
            "image_path": caminho,
            "updated_at": dados.get("updated_at"),
        }
    return saida


def _escrever_configuracao(repository: ConfigRepository, configuracao: dict) -> None:
    repository.config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(repository.config_file, "w", encoding="utf-8") as arquivo:
        json.dump(
            configuracao,
            arquivo,
            indent=4,
            ensure_ascii=False,
        )


def obter_preview_projeto_led(
    repository: ConfigRepository,
    nome_projeto: str | None,
) -> dict | None:
    nome = normalizar_nome_projeto_led(nome_projeto)
    if not nome:
        return None
    configuracao = repository.carregar_configuracao_existente_sem_alerta()
    dados = _obter_mapa_previews(configuracao).get(nome)
    return copy.deepcopy(dados) if isinstance(dados, dict) else None


def definir_preview_projeto_led(
    repository: ConfigRepository,
    nome_projeto: str | None,
    caminho_imagem: str,
) -> bool:
    nome = normalizar_nome_projeto_led(nome_projeto)
    caminho = str(caminho_imagem or "").strip()
    if not nome or not caminho:
        return False

    configuracao = repository.carregar_configuracao_existente_sem_alerta()
    if not isinstance(configuracao, dict):
        configuracao = {}

    previews = _obter_mapa_previews(configuracao)
    previews[nome] = {
        "image_path": caminho,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    configuracao[CHAVE_PREVIEWS_PROJETO] = previews
    _escrever_configuracao(repository, configuracao)
    return True


def instalar_preview_projeto_led_store() -> None:
    """Faz snapshots acompanharem renomeação/remoção sem alterar os projetos."""
    global _PATCH_INSTALADO
    if _PATCH_INSTALADO:
        return

    renomear_original = ConfigRepository.renomear_projeto_led
    remover_original = ConfigRepository.remover_projeto_led

    def renomear_projeto_led_com_preview(
        self: ConfigRepository,
        nome_atual: str,
        novo_nome: str,
    ) -> bool:
        atual = normalizar_nome_projeto_led(nome_atual)
        novo = normalizar_nome_projeto_led(novo_nome)
        sucesso = renomear_original(self, nome_atual, novo_nome)
        if not sucesso or not atual or not novo or atual == novo:
            return sucesso

        configuracao = self.carregar_configuracao_existente_sem_alerta()
        previews = _obter_mapa_previews(configuracao)
        if atual in previews:
            previews[novo] = previews.pop(atual)
            configuracao[CHAVE_PREVIEWS_PROJETO] = previews
            _escrever_configuracao(self, configuracao)
        return True

    def remover_projeto_led_com_preview(
        self: ConfigRepository,
        nome_projeto: str,
    ) -> bool:
        nome = normalizar_nome_projeto_led(nome_projeto)
        sucesso = remover_original(self, nome_projeto)
        if not sucesso or not nome:
            return sucesso

        configuracao = self.carregar_configuracao_existente_sem_alerta()
        previews = _obter_mapa_previews(configuracao)
        if nome in previews:
            previews.pop(nome, None)
            configuracao[CHAVE_PREVIEWS_PROJETO] = previews
            _escrever_configuracao(self, configuracao)
        return True

    ConfigRepository.renomear_projeto_led = renomear_projeto_led_com_preview
    ConfigRepository.remover_projeto_led = remover_projeto_led_com_preview
    _PATCH_INSTALADO = True
