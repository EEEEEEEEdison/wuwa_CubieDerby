from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable

from .movement import display_position, forward_path_positions, move_progress
from .runners import HIYUKI_ID, NPC_ID
from .skills import skill_enabled
from .tracing import TraceContext

AddGroupToPositionFn = Callable[..., None]
LogBlockFn = Callable[..., None]
LogGridFn = Callable[..., None]
MaybeArmAemeathPendingFn = Callable[..., None]
RecordHiyukiContactFn = Callable[..., None]
FormatRunnerFn = Callable[[int], str]


@dataclass(frozen=True)
class RunnerActionHelpers:
    add_group_to_position: AddGroupToPositionFn
    format_runner: FormatRunnerFn
    log_block: LogBlockFn
    log_grid: LogGridFn
    maybe_arm_aemeath_pending: MaybeArmAemeathPendingFn
    record_hiyuki_npc_path_contact: RecordHiyukiContactFn


def move_single_runner(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    player: int,
    total_steps: int,
    rng: random.Random,
    skill_state: Any | None = None,
    movement_state: Any | None = None,
    trace: TraceContext = False,
    helpers: RunnerActionHelpers,
) -> int:
    track_length = config.track_length
    current_progress = progress[player]
    current_pos = display_position(current_progress, track_length)
    grid[current_pos] = [runner for runner in grid[current_pos] if runner != player]
    new_progress = move_progress(current_progress, total_steps, track_length)
    if skill_state is not None and skill_enabled(config, HIYUKI_ID) and player == HIYUKI_ID and NPC_ID in progress:
        helpers.record_hiyuki_npc_path_contact(
            movers=[player],
            progress=progress,
            track_length=track_length,
            path=forward_path_positions(current_progress, total_steps, track_length),
            skill_state=skill_state,
            trace=trace,
        )
    helpers.add_group_to_position(
        grid,
        progress,
        [player],
        new_progress,
        rng,
        config,
        active_player=player,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
    )
    helpers.maybe_arm_aemeath_pending(
        movers=[player],
        start_progress=current_progress,
        end_progress=progress[player],
        moved_forward=True,
        config=config,
        skill_state=skill_state,
        trace=trace,
    )
    return progress[player]


def move_runner_with_left_side(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    player: int,
    idx_in_cell: int,
    total_steps: int,
    rng: random.Random,
    skill_state: Any | None = None,
    movement_state: Any | None = None,
    trace: TraceContext = False,
    helpers: RunnerActionHelpers,
) -> int:
    track_length = config.track_length
    current_progress = progress[player]
    current_pos = display_position(current_progress, track_length)
    old_cell = grid[current_pos]
    left_runners = old_cell[:idx_in_cell]
    movers = left_runners + [player]
    remaining = old_cell[idx_in_cell + 1 :]
    if remaining:
        grid[current_pos] = remaining
    else:
        grid.pop(current_pos, None)
    new_progress = move_progress(current_progress, total_steps, track_length)
    if skill_state is not None and skill_enabled(config, HIYUKI_ID) and HIYUKI_ID in movers and NPC_ID in progress:
        helpers.record_hiyuki_npc_path_contact(
            movers=movers,
            progress=progress,
            track_length=track_length,
            path=forward_path_positions(current_progress, total_steps, track_length),
            skill_state=skill_state,
            trace=trace,
        )
    helpers.add_group_to_position(
        grid,
        progress,
        movers,
        new_progress,
        rng,
        config,
        active_player=player,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
    )
    helpers.maybe_arm_aemeath_pending(
        movers=movers,
        start_progress=current_progress,
        end_progress=progress[player],
        moved_forward=True,
        config=config,
        skill_state=skill_state,
        trace=trace,
    )
    return progress[player]


def move_cantarella(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    player: int,
    total_steps: int,
    rng: random.Random,
    cantarella_state: int,
    cantarella_group: list[int],
    trace: TraceContext,
    skill_state: Any | None = None,
    movement_state: Any | None = None,
    helpers: RunnerActionHelpers,
) -> tuple[int, int, list[int]]:
    track_length = config.track_length
    new_progress = progress[player]
    group_mode = bool(cantarella_group)
    group = list(cantarella_group)

    for _ in range(total_steps):
        current_progress = progress[player]
        current_pos = display_position(current_progress, track_length)
        old_cell = list(grid[current_pos])
        if group_mode:
            movers = [runner for runner in group if display_position(progress[runner], track_length) == current_pos]
            if not movers:
                movers = [player]
        else:
            idx = old_cell.index(player)
            movers = old_cell[:idx] + [player]

        grid[current_pos] = [runner for runner in grid[current_pos] if runner not in movers]
        new_progress = move_progress(current_progress, 1, track_length)
        new_pos = display_position(new_progress, track_length)
        if skill_state is not None and skill_enabled(config, HIYUKI_ID) and HIYUKI_ID in movers and NPC_ID in progress:
            helpers.record_hiyuki_npc_path_contact(
                movers=movers,
                progress=progress,
                track_length=track_length,
                path=forward_path_positions(current_progress, 1, track_length),
                skill_state=skill_state,
                trace=trace,
            )
        helpers.add_group_to_position(
            grid,
            progress,
            movers,
            new_progress,
            rng,
            config,
            active_player=player,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )
        helpers.maybe_arm_aemeath_pending(
            movers=movers,
            start_progress=current_progress,
            end_progress=progress[player],
            moved_forward=True,
            config=config,
            skill_state=skill_state,
            trace=trace,
        )
        new_progress = progress[player]
        new_pos = display_position(new_progress, track_length)
        if trace:
            helpers.log_grid(trace, grid)

        if not group_mode:
            old_set = set(old_cell)
            if any(runner not in old_set for runner in grid[new_pos]):
                group_mode = True
                group = list(grid[new_pos])
                cantarella_state = 2
                if trace:
                    helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：与终点格角色合流")

        if new_progress >= track_length:
            break

    return new_progress, cantarella_state, group
