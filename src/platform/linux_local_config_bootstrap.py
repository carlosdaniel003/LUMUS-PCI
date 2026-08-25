from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


ODIN_CONFIG_DIR_ENV = "ODIN_CONFIG_DIR"
ODIN_LOCAL_DIRNAME = "odin"
ODIN_CONFIG_FILENAME = "odin_pci_config.json"
ODIN_MIGRATION_BACKUP_FILENAME = "odin_pci_config.legacy_backup.json"


def caminho_config_local_linux(
    home: Path | None = None,
    xdg_config_home: str | os.PathLike[str] | None = None,
) -> Path:
    """Retorna a pasta de configuração persistente do JIG fora do repositório."""
    if xdg_config_home:
        base = Path(xdg_config_home).expanduser()
    else:
        base = (home or Path.home()).expanduser() / ".config"
    return base / ODIN_LOCAL_DIRNAME


def _copiar_apenas_ausentes(origem: Path, destino: Path) -> None:
    if not origem.exists():
        return
    destino.mkdir(parents=True, exist_ok=True)
    for item in origem.rglob("*"):
        relativo = item.relative_to(origem)
        alvo = destino / relativo
        if item.is_dir():
            alvo.mkdir(parents=True, exist_ok=True)
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not alvo.exists():
            shutil.copy2(item, alvo)


def _reescrever_caminhos_config(
    valor,
    legacy_dir: Path,
    local_dir: Path,
    project_dir: Path,
):
    if isinstance(valor, dict):
        return {
            chave: _reescrever_caminhos_config(
                item,
                legacy_dir,
                local_dir,
                project_dir,
            )
            for chave, item in valor.items()
        }
    if isinstance(valor, list):
        return [
            _reescrever_caminhos_config(
                item,
                legacy_dir,
                local_dir,
                project_dir,
            )
            for item in valor
        ]
    if not isinstance(valor, str) or not valor.strip():
        return valor

    texto = valor.strip()
    legacy_abs = legacy_dir.resolve()
    local_abs = local_dir.resolve()

    try:
        candidato = Path(texto).expanduser()
        if candidato.is_absolute():
            candidato_abs = candidato.resolve()
            try:
                relativo = candidato_abs.relative_to(legacy_abs)
            except ValueError:
                relativo = None
            if relativo is not None:
                return str(local_abs / relativo)
    except Exception:
        pass

    normalizado = texto.replace("\\", "/")
    prefixos = (
        "data/config/",
        str((project_dir / "data" / "config").resolve()).replace("\\", "/") + "/",
    )
    for prefixo in prefixos:
        if normalizado.startswith(prefixo):
            relativo = normalizado[len(prefixo):]
            return str(local_abs / Path(relativo))
    return valor


def _migrar_json(
    config_file: Path,
    legacy_dir: Path,
    local_dir: Path,
    project_dir: Path,
) -> None:
    if not config_file.exists():
        return
    try:
        with open(config_file, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return
    if not isinstance(dados, dict):
        return

    migrado = _reescrever_caminhos_config(
        dados,
        legacy_dir=legacy_dir,
        local_dir=local_dir,
        project_dir=project_dir,
    )
    if migrado == dados:
        return

    backup = local_dir / ODIN_MIGRATION_BACKUP_FILENAME
    if not backup.exists():
        try:
            shutil.copy2(config_file, backup)
        except Exception:
            pass

    temporario = config_file.with_suffix(config_file.suffix + ".tmp")
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(migrado, arquivo, indent=4, ensure_ascii=False)
    temporario.replace(config_file)


def preparar_configuracao_local_linux(
    project_dir: Path,
    *,
    home: Path | None = None,
    xdg_config_home: str | os.PathLike[str] | None = None,
    environment: dict[str, str] | None = None,
) -> Path:
    """Prepara a configuração persistente do JIG antes de importar o app.

    A primeira execução copia a configuração legada do repositório. Nas
    execuções seguintes, arquivos locais nunca são sobrescritos pela cópia
    legada. Isso impede que uma atualização Git restaure máscaras antigas.
    """
    projeto = Path(project_dir).resolve()
    legacy_dir = projeto / "data" / "config"
    env = environment if environment is not None else os.environ

    configurado = str(env.get(ODIN_CONFIG_DIR_ENV, "")).strip()
    if configurado:
        local_dir = Path(configurado).expanduser()
    else:
        xdg = xdg_config_home
        if xdg is None:
            xdg = env.get("XDG_CONFIG_HOME")
        local_dir = caminho_config_local_linux(home=home, xdg_config_home=xdg)
        env[ODIN_CONFIG_DIR_ENV] = str(local_dir)

    local_dir.mkdir(parents=True, exist_ok=True)
    local_config = local_dir / ODIN_CONFIG_FILENAME
    legacy_config = legacy_dir / ODIN_CONFIG_FILENAME

    if not local_config.exists() and legacy_config.exists():
        _copiar_apenas_ausentes(legacy_dir, local_dir)
    else:
        # Referências antigas ainda podem estar apenas em data/config. Copiamos
        # somente o que estiver ausente; nunca substituímos um arquivo local.
        _copiar_apenas_ausentes(legacy_dir, local_dir)

    _migrar_json(
        local_config,
        legacy_dir=legacy_dir,
        local_dir=local_dir,
        project_dir=projeto,
    )
    return local_dir
