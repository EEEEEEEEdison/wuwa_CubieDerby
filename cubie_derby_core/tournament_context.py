from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cubie_derby_core.tournament import (
    TournamentEntryRequest,
    build_tournament_entry_request,
    get_tournament_entry_point_definition,
    tournament_entry_input_context,
    tournament_input_snapshot_to_dict,
)


TOURNAMENT_CONTEXT_SCHEMA_VERSION = 1


def tournament_entry_request_to_dict(request: TournamentEntryRequest) -> dict[str, object]:
    definition = get_tournament_entry_point_definition(request.season, request.entry_point)
    inputs: dict[str, object] = {}
    for requirement in definition.requirements:
        value = request.inputs.get(requirement.key)
        if value is None:
            continue
        if requirement.kind == "grouped-entrants":
            inputs[requirement.key] = [list(group) for group in value]  # type: ignore[misc]
        else:
            inputs[requirement.key] = list(value)  # type: ignore[arg-type]
    return {
        "schema_version": TOURNAMENT_CONTEXT_SCHEMA_VERSION,
        "season": request.season,
        "entry_point": definition.key,
        "entry_label": definition.label,
        "inputs": inputs,
        "input_context": [
            tournament_input_snapshot_to_dict(snapshot)
            for snapshot in tournament_entry_input_context(request)
        ],
    }


def tournament_entry_request_from_dict(data: Any) -> TournamentEntryRequest:
    if not isinstance(data, dict):
        raise ValueError("tournament context JSON must be an object")
    season = data.get("season")
    if not isinstance(season, int):
        raise ValueError("tournament context season must be an integer")
    entry_point = data.get("entry_point")
    if not isinstance(entry_point, str) or not entry_point:
        raise ValueError("tournament context entry_point must be a non-empty string")
    raw_inputs = data.get("inputs")
    if not isinstance(raw_inputs, dict):
        raise ValueError("tournament context inputs must be an object")
    inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        if not isinstance(key, str):
            raise ValueError("tournament context input keys must be strings")
        inputs[key] = value
    return build_tournament_entry_request(
        season=season,
        entry_point=entry_point,
        inputs=inputs,
    )


def load_tournament_entry_request(path: str | Path) -> TournamentEntryRequest:
    context_path = Path(path)
    return tournament_entry_request_from_dict(
        json.loads(context_path.read_text(encoding="utf-8"))
    )


def save_tournament_entry_request(
    request: TournamentEntryRequest,
    path: str | Path,
) -> None:
    context_path = Path(path)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        json.dumps(
            tournament_entry_request_to_dict(request),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
