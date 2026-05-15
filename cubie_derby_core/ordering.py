from __future__ import annotations

import random
from typing import Callable, Iterable, Sequence

from .movement import keep_npc_rightmost, remove_runner_from_grid
from .runners import NPC_ID

ValidateSameRunnersFn = Callable[[Sequence[int], Sequence[int], str], None]
FormatRunnerFn = Callable[[int], str]


def initial_player_order(
    config: object,
    grid: dict[int, Sequence[int]],
    rng: random.Random,
    *,
    validate_same_runners_fn: ValidateSameRunnersFn,
) -> list[int]:
    if getattr(config, "initial_order_mode") == "random":
        order = list(getattr(config, "runners"))
        rng.shuffle(order)
        return order
    if getattr(config, "initial_order_mode") == "start":
        order = [runner for _, cell in sorted(grid.items()) for runner in cell if runner != NPC_ID]
        validate_same_runners_fn(getattr(config, "runners"), order, "initial start order")
        return order
    if getattr(config, "initial_order_mode") == "fixed":
        return list(getattr(config, "fixed_initial_order"))
    raise ValueError(f"unknown initial_order_mode: {getattr(config, 'initial_order_mode')}")


def rank_scope(runners: Sequence[int], progress: dict[int, int], include_npc: bool) -> tuple[int, ...]:
    if include_npc and NPC_ID in progress:
        return tuple(runners) + (NPC_ID,)
    return tuple(runners)


def next_round_action_order(
    *,
    runners: Sequence[int],
    rng: random.Random,
    include_npc: bool,
    forced_last_runners: Sequence[int] = (),
) -> list[int]:
    order = list(runners)
    if include_npc:
        order.append(NPC_ID)
    rng.shuffle(order)
    trailing: list[int] = []
    trailing_set: set[int] = set()
    for runner in forced_last_runners:
        if runner in order and runner not in trailing_set:
            trailing.append(runner)
            trailing_set.add(runner)
    if trailing:
        order = [runner for runner in order if runner not in trailing_set] + trailing
    return order


def add_npc_to_start(grid: dict[int, list[int]]) -> None:
    remove_runner_from_grid(grid, NPC_ID)
    if grid.get(0):
        grid[0] = list(grid[0]) + [NPC_ID]
    else:
        grid[0] = [NPC_ID]
    keep_npc_rightmost(grid[0])


def format_round_dice(
    round_dice: dict[int, int],
    player_order: Sequence[int],
    *,
    format_runner_fn: FormatRunnerFn,
) -> str:
    return "；".join(f"{format_runner_fn(player)}={round_dice[player]}" for player in player_order if player in round_dice)


def current_rank(runners: Sequence[int], progress: dict[int, int], grid: dict[int, Sequence[int]]) -> list[int]:
    cell_index: dict[int, int] = {}
    for cell in grid.values():
        for idx, runner in enumerate(cell):
            if runner != NPC_ID:
                cell_index[runner] = idx
    progress_get = progress.__getitem__
    cell_index_get = cell_index.get
    return sorted(runners, key=lambda runner: (-progress_get(runner), cell_index_get(runner, 9999)))
