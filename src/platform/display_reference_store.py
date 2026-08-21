from __future__ import annotations

import copy
import json
from dataclasses import fields
from pathlib import Path
from uuid import uuid4
import math

from src.models.led_features import LedFeatures
from src.platform.display_project_repository import normalizar_nome_projeto_display


MAX_DISPLAY_REFERENCES_PER_STATE = 3
DISPLAY_REFERENCE_TYPES = ("on", "off", "low_light")
DISPLAY_REFERENCE_LABELS = {
    "on": "ACESO",
    "off": "APAGADO",
    "low_light": "POUCA LUZ",
}
DISPLAY_REFERENCE_SCHEMA_VERSION = 1
DEFAULT_DISPLAY_REFERENCE_FILE = Path("data/config/odin_display_learning.json")


class DisplayReferenceLimitError(ValueError):
    pass


def display_learning_path_for_repository(repository) -> Path:
    config_file = Path(getattr(repository, "config_file", "") or "")
    if config_file.name == "odin_display_projects.json":
        return config_file.with_name("odin_display_learning.json")
    if config_file.name:
        return config_file.with_name(f"{config_file.stem}_learning.json")
    return DEFAULT_DISPLAY_REFERENCE_FILE


def _empty_group() -> dict[str, list[dict]]:
    return {tipo: [] for tipo in DISPLAY_REFERENCE_TYPES}


def _valid_sample(sample) -> bool:
    return isinstance(sample, dict) and bool(
        sample.get("image_path") or sample.get("features")
    )


def normalize_display_reference_sample(sample: dict | None) -> dict | None:
    if not _valid_sample(sample):
        return None
    data = copy.deepcopy(sample)
    data["id"] = str(data.get("id") or uuid4().hex)
    data["image_path"] = str(data.get("image_path") or "")
    data["features"] = (
        copy.deepcopy(data.get("features"))
        if isinstance(data.get("features"), dict)
        else {}
    )
    mask = data.get("mask")
    if not isinstance(mask, dict):
        data.pop("mask", None)
    return data


def _normalize_group(group) -> dict[str, list[dict]]:
    source = group if isinstance(group, dict) else {}
    result = _empty_group()
    for tipo in DISPLAY_REFERENCE_TYPES:
        items = source.get(tipo, [])
        if not isinstance(items, list):
            continue
        for item in items[:MAX_DISPLAY_REFERENCES_PER_STATE]:
            normalized = normalize_display_reference_sample(item)
            if normalized is not None:
                result[tipo].append(normalized)
    return result


def aggregate_display_reference_features(samples: list[dict]) -> LedFeatures | None:
    """Mesmo aprendizado por centróide usado no fluxo de referências do F2.

    A implementação fica local ao Display para que o F3 não dependa do runtime
    ou do armazenamento do PCI LED.
    """
    feature_objects: list[LedFeatures] = []
    for entry in samples or ():
        sample = entry.get("sample", entry) if isinstance(entry, dict) else {}
        features_data = sample.get("features", {}) if isinstance(sample, dict) else {}
        if isinstance(features_data, dict) and features_data:
            feature_objects.append(LedFeatures.from_dict(features_data))
    if not feature_objects:
        return None

    values = {}
    integer_fields = {"area_pixels", "inner_area_pixels", "ring_area_pixels"}
    for field in fields(LedFeatures):
        name = field.name
        numbers = [float(getattr(item, name, 0.0)) for item in feature_objects]
        if name == "h_mean":
            sines = [math.sin((value / 180.0) * 2.0 * math.pi) for value in numbers]
            cosines = [math.cos((value / 180.0) * 2.0 * math.pi) for value in numbers]
            angle = math.atan2(
                sum(sines) / len(sines),
                sum(cosines) / len(cosines),
            )
            if angle < 0:
                angle += 2.0 * math.pi
            average = (angle / (2.0 * math.pi)) * 180.0
        else:
            average = sum(numbers) / len(numbers)
        values[name] = int(round(average)) if name in integer_fields else float(average)
    return LedFeatures(**values)


class DisplayReferenceLearningStore:
    """Biblioteca de referências exclusiva dos Projetos Display/F3."""

    def __init__(self, config_file: str | Path | None = None) -> None:
        self.config_file = Path(config_file or DEFAULT_DISPLAY_REFERENCE_FILE)

    @staticmethod
    def _empty_structure() -> dict:
        return {
            "schema_version": DISPLAY_REFERENCE_SCHEMA_VERSION,
            "global": _empty_group(),
            "projects": {},
        }

    def _normalize(self, data) -> dict:
        source = data if isinstance(data, dict) else {}
        projects = {}
        source_projects = source.get("projects", {})
        if isinstance(source_projects, dict):
            for raw_name, raw_group in source_projects.items():
                name = normalizar_nome_projeto_display(raw_name)
                if name:
                    projects[name] = _normalize_group(raw_group)
        return {
            "schema_version": DISPLAY_REFERENCE_SCHEMA_VERSION,
            "global": _normalize_group(source.get("global")),
            "projects": projects,
        }

    def _read(self) -> dict:
        if not self.config_file.exists():
            return self._empty_structure()
        try:
            with open(self.config_file, "r", encoding="utf-8") as file:
                return self._normalize(json.load(file))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return self._empty_structure()

    def _write(self, data: dict) -> None:
        normalized = self._normalize(data)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_file.with_suffix(self.config_file.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=4, ensure_ascii=False)
            file.flush()
        temporary.replace(self.config_file)

    def _project_group(self, data: dict, project: str, create: bool = False):
        name = normalizar_nome_projeto_display(project)
        if not name:
            return _empty_group()
        projects = data.setdefault("projects", {})
        group = projects.get(name)
        if not isinstance(group, dict):
            group = _empty_group()
            if create:
                projects[name] = group
        normalized = _normalize_group(group)
        if create:
            projects[name] = normalized
        return normalized

    def active_references(self, project: str | None, tipo: str) -> list[dict]:
        if tipo not in DISPLAY_REFERENCE_TYPES:
            return []
        data = self._read()
        result: list[dict] = []
        for index, sample in enumerate(data["global"][tipo]):
            result.append({
                "scope": "global",
                "index": index,
                "sample": copy.deepcopy(sample),
            })
        local = self._project_group(data, project or "", create=False)[tipo]
        for index, sample in enumerate(local):
            if len(result) >= MAX_DISPLAY_REFERENCES_PER_STATE:
                break
            result.append({
                "scope": "project",
                "index": index,
                "sample": copy.deepcopy(sample),
            })
        return result

    def learned_features(self, project: str | None, tipo: str) -> LedFeatures | None:
        return aggregate_display_reference_features(
            self.active_references(project, tipo)
        )

    def learning_snapshot(self, project: str | None) -> dict:
        result = {}
        for tipo in DISPLAY_REFERENCE_TYPES:
            active = self.active_references(project, tipo)
            learned = aggregate_display_reference_features(active)
            result[tipo] = {
                "count": len(active),
                "references": active,
                "features": learned.to_dict() if learned is not None else None,
            }
        return result

    def _validate_new_global(self, data: dict, tipo: str) -> None:
        new_global_count = len(data["global"][tipo]) + 1
        if new_global_count > MAX_DISPLAY_REFERENCES_PER_STATE:
            raise DisplayReferenceLimitError(
                f"Já existem {MAX_DISPLAY_REFERENCES_PER_STATE} referências globais para {DISPLAY_REFERENCE_LABELS[tipo]}."
            )
        for project_name, project_group in data.get("projects", {}).items():
            local_count = len(_normalize_group(project_group)[tipo])
            if new_global_count + local_count > MAX_DISPLAY_REFERENCES_PER_STATE:
                raise DisplayReferenceLimitError(
                    f"A nova referência global faria o projeto {project_name} ultrapassar o limite de {MAX_DISPLAY_REFERENCES_PER_STATE} referências ativas."
                )

    def _validate_new_project(self, data: dict, project: str, tipo: str) -> None:
        name = normalizar_nome_projeto_display(project)
        if not name:
            raise ValueError("Selecione um Projeto Display antes de salvar referência de projeto.")
        global_count = len(data["global"][tipo])
        local_count = len(self._project_group(data, name, create=False)[tipo])
        if global_count + local_count + 1 > MAX_DISPLAY_REFERENCES_PER_STATE:
            raise DisplayReferenceLimitError(
                f"O projeto {name} já atingiu o limite de {MAX_DISPLAY_REFERENCES_PER_STATE} referências ativas para {DISPLAY_REFERENCE_LABELS[tipo]}."
            )

    def save_sample(
        self,
        project: str | None,
        tipo: str,
        sample: dict,
        scope: str = "project",
        index: int | None = None,
    ) -> dict:
        if tipo not in DISPLAY_REFERENCE_TYPES:
            raise ValueError("Tipo de referência Display inválido.")
        normalized_sample = normalize_display_reference_sample(sample)
        if normalized_sample is None:
            raise ValueError("Amostra de referência Display inválida.")

        data = self._read()
        target_scope = "global" if str(scope).lower() == "global" else "project"
        if target_scope == "global":
            group = data["global"][tipo]
            if index is None:
                self._validate_new_global(data, tipo)
                group.append(normalized_sample)
            else:
                idx = int(index)
                if idx < 0 or idx >= len(group):
                    raise IndexError("Referência global Display não encontrada.")
                normalized_sample["id"] = str(group[idx].get("id") or normalized_sample["id"])
                group[idx] = normalized_sample
        else:
            name = normalizar_nome_projeto_display(project)
            if not name:
                raise ValueError("Selecione um Projeto Display antes de salvar referência de projeto.")
            group = self._project_group(data, name, create=True)[tipo]
            if index is None:
                self._validate_new_project(data, name, tipo)
                group.append(normalized_sample)
            else:
                idx = int(index)
                if idx < 0 or idx >= len(group):
                    raise IndexError("Referência de projeto Display não encontrada.")
                normalized_sample["id"] = str(group[idx].get("id") or normalized_sample["id"])
                group[idx] = normalized_sample
            data["projects"][name] = {
                **_normalize_group(data["projects"].get(name)),
                tipo: group,
            }

        self._write(data)
        return copy.deepcopy(normalized_sample)

    def remove_sample(
        self,
        project: str | None,
        tipo: str,
        scope: str,
        index: int,
    ) -> dict | None:
        if tipo not in DISPLAY_REFERENCE_TYPES:
            return None
        data = self._read()
        target_scope = "global" if str(scope).lower() == "global" else "project"
        if target_scope == "global":
            group = data["global"][tipo]
        else:
            name = normalizar_nome_projeto_display(project)
            if not name or name not in data.get("projects", {}):
                return None
            group = self._project_group(data, name, create=True)[tipo]
        idx = int(index)
        if idx < 0 or idx >= len(group):
            return None
        removed = group.pop(idx)
        if target_scope == "project":
            data["projects"][name] = {
                **_normalize_group(data["projects"].get(name)),
                tipo: group,
            }
        self._write(data)
        return copy.deepcopy(removed)

    def move_scope(
        self,
        project: str | None,
        tipo: str,
        current_scope: str,
        index: int,
    ) -> None:
        current = "global" if str(current_scope).lower() == "global" else "project"
        destination = "project" if current == "global" else "global"
        data_backup = self._read()
        removed = self.remove_sample(project, tipo, current, index)
        if removed is None:
            raise IndexError("Referência Display não encontrada.")
        try:
            self.save_sample(project, tipo, removed, scope=destination)
        except Exception:
            self._write(data_backup)
            raise

    def rename_project(self, old_name: str, new_name: str) -> None:
        old = normalizar_nome_projeto_display(old_name)
        new = normalizar_nome_projeto_display(new_name)
        if not old or not new or old == new:
            return
        data = self._read()
        if old not in data.get("projects", {}):
            return
        data["projects"][new] = data["projects"].pop(old)
        self._write(data)

    def remove_project(self, project: str) -> None:
        name = normalizar_nome_projeto_display(project)
        if not name:
            return
        data = self._read()
        if name in data.get("projects", {}):
            data["projects"].pop(name, None)
            self._write(data)
