from __future__ import annotations

import random
from typing import Iterable, Sequence

from .runners import NPC_ID


MIN_START_POSITION = -3


def validate_start_position(pos: int, track_length: int) -> None:
    if pos < MIN_START_POSITION or pos >= track_length:
        raise ValueError(
            f"start position {pos} is outside the track; "
            f"expected {MIN_START_POSITION}..{track_length - 1}"
        )


def display_position(progress: int, track_length: int) -> int:
    return progress if progress < 0 else progress % track_length


def move_progress(current_progress: int, steps: int, track_length: int) -> int:
    target = current_progress + steps
    return track_length if target >= track_length else target


def move_progress_by_delta(current_progress: int, signed_steps: int, track_length: int) -> int:
    if signed_steps >= 0:
        return move_progress(current_progress, signed_steps, track_length)
    return max(MIN_START_POSITION, current_progress + signed_steps)


def remove_runner_from_grid(grid: dict[int, list[int]], runner: int) -> None:
    empty_position: int | None = None
    for pos, cell in grid.items():
        try:
            runner_index = cell.index(runner)
        except ValueError:
            continue
        del cell[runner_index]
        if not cell:
            empty_position = pos
        break
    if empty_position is not None:
        grid.pop(empty_position, None)


def keep_npc_rightmost(cell: list[int]) -> None:
    if not cell or NPC_ID not in cell:
        return
    if cell[-1] == NPC_ID and NPC_ID not in cell[:-1]:
        return
    write = 0
    npc_count = 0
    for runner in cell:
        if runner == NPC_ID:
            npc_count += 1
        else:
            cell[write] = runner
            write += 1
    cell[write:] = [NPC_ID] * npc_count


def shuffle_without_npc(cell: Sequence[int], rng: random.Random) -> list[int]:
    runners: list[int] = []
    npc_count = 0
    for runner in cell:
        if runner == NPC_ID:
            npc_count += 1
        else:
            runners.append(runner)
    rng.shuffle(runners)
    return runners + [NPC_ID] * npc_count


def forward_path_positions(current_progress: int, steps: int, track_length: int) -> Iterable[int]:
    if steps <= 0:
        return
    final_progress = min(current_progress + steps, track_length)
    for progress_value in range(current_progress + 1, final_progress + 1):
        yield display_position(progress_value, track_length)


def cell_effect_path_positions(
    *,
    start_progress: int,
    delta: int,
    track_length: int,
    wrap: bool,
) -> Iterable[int]:
    if delta == 0:
        return
    if wrap:
        direction = 1 if delta > 0 else -1
        for offset in range(1, abs(delta) + 1):
            yield (start_progress + direction * offset) % track_length
        return
    if delta > 0:
        yield from forward_path_positions(start_progress, delta, track_length)
        return
    final_progress = max(MIN_START_POSITION, start_progress + delta)
    for progress_value in range(start_progress - 1, final_progress - 1, -1):
        yield display_position(progress_value, track_length)


def npc_reverse_path_positions(npc_progress: int, steps: int, track_length: int) -> Iterable[int]:
    for offset in range(1, steps + 1):
        yield (npc_progress - offset) % track_length
