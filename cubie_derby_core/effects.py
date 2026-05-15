from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol, Sequence

from .movement import (
    MIN_START_POSITION,
    cell_effect_path_positions,
    display_position,
    keep_npc_rightmost,
    move_progress,
    shuffle_without_npc,
)
from .runners import HIYUKI_ID, LUUK_HERSSEN_ID, NPC_ID
from .skills import record_skill_success, skill_enabled, skill_enabled_from_set
from .tracing import TraceContext


class EffectConfig(Protocol):
    track_length: int
    shuffle_cells: frozenset[int]
    forward_cells: frozenset[int]
    backward_cells: frozenset[int]
    disabled_skills: frozenset[int]


@dataclass(frozen=True)
class EffectHooks:
    record_movement: Callable[..., None]
    record_hiyuki_npc_path_contact: Callable[..., None]
    maybe_arm_aemeath_pending: Callable[..., None]
    format_position: Callable[[int], str]
    format_cell: Callable[[Iterable[int]], str]
    format_runner: Callable[[int], str]
    log_block: Callable[..., None]
    log_timing: Callable[..., None]


def add_group_to_position(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    new_progress: int,
    rng: random.Random,
    config: EffectConfig,
    *,
    hooks: EffectHooks,
    active_player: int | None = None,
    skill_state: object | None = None,
    movement_state: object | None = None,
    trace: TraceContext = False,
    apply_effects: bool = True,
) -> None:
    if not movers:
        return
    track_length = config.track_length
    new_pos = display_position(new_progress, track_length)
    movers_list = list(movers)
    if movement_state is not None:
        for runner in movers_list:
            if runner <= 0:
                continue
            distance = max(0, new_progress - progress[runner])
            if distance <= 0:
                continue
            movement_state.total_steps[runner] = movement_state.total_steps.get(runner, 0) + distance
            if active_player is not None and runner != active_player:
                movement_state.carried_steps[runner] = movement_state.carried_steps.get(runner, 0) + distance
    for runner in movers:
        progress[runner] = new_progress
    destination_cell = grid.get(new_pos)
    if destination_cell is None:
        destination_cell = movers_list
        grid[new_pos] = destination_cell
    else:
        destination_cell[:0] = movers_list
    keep_npc_rightmost(destination_cell)
    if trace:
        hooks.log_block(
            trace,
            "落点结算：",
            f"移动队列：{hooks.format_cell(movers)}",
            f"到达位置：{hooks.format_position(new_pos)}",
            f"格内顺序：{hooks.format_cell(destination_cell)}",
        )
    if apply_effects:
        apply_cell_effects(
            grid,
            progress,
            movers,
            new_pos,
            rng,
            config,
            hooks=hooks,
            active_player=active_player,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )


def apply_cell_effects(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    pos: int,
    rng: random.Random,
    config: EffectConfig,
    *,
    hooks: EffectHooks,
    active_player: int | None = None,
    skill_state: object | None = None,
    movement_state: object | None = None,
    trace: TraceContext = False,
) -> None:
    if trace and (pos in config.shuffle_cells or pos in config.forward_cells or pos in config.backward_cells):
        hooks.log_timing(trace, "落点结算后", f"检查{hooks.format_position(pos)}的赛道特殊格效果")
    if pos in config.shuffle_cells:
        apply_shuffle_cell_effect(grid, pos, rng, hooks=hooks, trace=trace)
    if pos in config.forward_cells:
        move_group_due_to_cell_effect(
            grid,
            progress,
            movers,
            pos,
            1,
            rng,
            config,
            hooks=hooks,
            active_player=active_player,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )
    elif pos in config.backward_cells:
        move_group_due_to_cell_effect(
            grid,
            progress,
            movers,
            pos,
            -1,
            rng,
            config,
            hooks=hooks,
            active_player=active_player,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )


def move_group_due_to_cell_effect(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    current_pos: int,
    delta: int,
    rng: random.Random,
    config: EffectConfig,
    *,
    hooks: EffectHooks,
    active_player: int | None = None,
    skill_state: object | None = None,
    movement_state: object | None = None,
    trace: TraceContext = False,
) -> None:
    active_movers = [runner for runner in movers if runner in grid.get(current_pos, [])]
    if not active_movers:
        return
    delta = adjust_cell_effect_delta(
        active_player,
        delta,
        hooks=hooks,
        disabled_skills=config.disabled_skills,
        skill_state=skill_state,
        trace=trace,
    )
    current_cell = grid[current_pos]
    if len(active_movers) == len(current_cell):
        grid.pop(current_pos, None)
    elif len(active_movers) == 1:
        current_cell.remove(active_movers[0])
    else:
        active_mover_set = set(active_movers)
        write_index = 0
        for runner in current_cell:
            if runner not in active_mover_set:
                current_cell[write_index] = runner
                write_index += 1
        del current_cell[write_index:]
        if not current_cell:
            grid.pop(current_pos, None)

    base_progress = progress[active_movers[-1]]
    if active_movers == [NPC_ID]:
        new_progress = (base_progress + delta) % config.track_length
    elif delta > 0:
        new_progress = move_progress(base_progress, delta, config.track_length)
    else:
        new_progress = max(MIN_START_POSITION, base_progress + delta)
    new_pos = display_position(new_progress, config.track_length)
    if skill_state is not None and skill_enabled(config, HIYUKI_ID) and (
        (HIYUKI_ID in active_movers and NPC_ID in progress)
        or (active_movers == [NPC_ID] and HIYUKI_ID in progress)
    ):
        hooks.record_hiyuki_npc_path_contact(
            movers=active_movers,
            progress=progress,
            track_length=config.track_length,
            path=cell_effect_path_positions(
                start_progress=base_progress,
                delta=delta,
                track_length=config.track_length,
                wrap=active_movers == [NPC_ID],
            ),
            skill_state=skill_state,
            trace=trace,
        )
    for runner in active_movers:
        hooks.record_movement(
            movement_state,
            [runner],
            max(0, new_progress - progress[runner]),
            active_player=active_player,
        )
    for runner in active_movers:
        progress[runner] = new_progress
    destination_cell = grid.get(new_pos)
    if destination_cell is None:
        destination_cell = list(active_movers)
        grid[new_pos] = destination_cell
    else:
        destination_cell[:0] = active_movers
    keep_npc_rightmost(destination_cell)
    hooks.maybe_arm_aemeath_pending(
        movers=active_movers,
        start_progress=base_progress,
        end_progress=new_progress,
        moved_forward=delta > 0,
        config=config,
        skill_state=skill_state,
        trace=trace,
    )
    direction_text = f"前进{delta}格" if delta > 0 else f"后退{-delta}格"
    if trace:
        hooks.log_block(
            trace,
            f"特殊格{hooks.format_position(current_pos)}：",
            f"效果：{direction_text}",
            f"移动队列：{hooks.format_cell(active_movers)}",
            f"到达位置：{hooks.format_position(new_pos)}",
            f"格内顺序：{hooks.format_cell(destination_cell)}",
        )


def apply_shuffle_cell_effect(
    grid: dict[int, list[int]],
    pos: int,
    rng: random.Random,
    *,
    hooks: EffectHooks,
    trace: TraceContext = False,
) -> None:
    before = list(grid[pos]) if trace else ()
    grid[pos] = shuffle_without_npc(grid[pos], rng)
    if trace:
        hooks.log_block(
            trace,
            f"特殊格{hooks.format_position(pos)}：",
            "效果：随机打乱格内顺序",
            f"打乱对象：{hooks.format_cell([runner for runner in before if runner != NPC_ID])}",
            "NPC处理：不参与打乱，结算后固定最右",
            f"打乱前：{hooks.format_cell(before)}",
            f"打乱后：{hooks.format_cell(grid[pos])}",
        )


def adjust_cell_effect_delta(
    active_player: int | None,
    delta: int,
    *,
    hooks: EffectHooks,
    disabled_skills: frozenset[int] = frozenset(),
    skill_state: object | None = None,
    trace: TraceContext = False,
) -> int:
    if active_player != LUUK_HERSSEN_ID or not skill_enabled_from_set(disabled_skills, LUUK_HERSSEN_ID):
        return delta
    adjusted = 4 if delta > 0 else -2
    record_skill_success(skill_state, LUUK_HERSSEN_ID)
    if trace:
        hooks.log_block(
            trace,
            f"{hooks.format_runner(LUUK_HERSSEN_ID)}技能触发：",
            f"特殊格原效果：{'前进1格' if delta > 0 else '后退1格'}",
            f"修正后效果：{'前进4格' if adjusted > 0 else '后退2格'}",
        )
    return adjusted
