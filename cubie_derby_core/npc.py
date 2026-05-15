from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from .movement import display_position, keep_npc_rightmost, remove_runner_from_grid
from .runners import HIYUKI_ID, NPC_ID
from .skills import skill_enabled
from .tracing import TraceContext

ApplyCellEffectsFn = Callable[..., None]
CurrentRankFn = Callable[[Sequence[int], dict[int, int], dict[int, Sequence[int]]], list[int]]
FormatCellFn = Callable[[Iterable[int]], str]
FormatPositionFn = Callable[[int], str]
FormatRunnerFn = Callable[[int], str]
RecordHiyukiContactFn = Callable[..., None]
TraceLogFn = Callable[..., None]


@dataclass(frozen=True)
class NPCHelpers:
    apply_cell_effects: ApplyCellEffectsFn
    current_rank: CurrentRankFn
    format_cell: FormatCellFn
    format_position: FormatPositionFn
    format_runner: FormatRunnerFn
    log_block: TraceLogFn
    record_hiyuki_npc_path_contact: RecordHiyukiContactFn


def move_npc(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    npc_progress: int,
    rng: random.Random,
    trace: TraceContext,
    steps: int | None = None,
    skill_state: Any | None = None,
    movement_state: Any | None = None,
    ignore_waiting_stack: bool = False,
    helpers: NPCHelpers,
) -> int:
    track_length = config.track_length
    steps = rng.randint(1, 6) if steps is None else steps
    current_pos = npc_progress % track_length
    current_cell = grid.get(current_pos, [])
    if current_cell:
        keep_npc_rightmost(current_cell)
    if NPC_ID in current_cell:
        if ignore_waiting_stack:
            remaining = [runner for runner in current_cell if runner != NPC_ID]
            if remaining:
                grid[current_pos] = remaining
            else:
                grid.pop(current_pos, None)
            movers = [NPC_ID]
        else:
            npc_idx = current_cell.index(NPC_ID)
            movers = current_cell[:npc_idx] + [NPC_ID]
            remaining = current_cell[npc_idx + 1 :]
            if remaining:
                grid[current_pos] = remaining
            else:
                grid.pop(current_pos, None)
    else:
        remove_runner_from_grid(grid, NPC_ID)
        movers = [NPC_ID]

    path = [current_pos]
    contact_cell: list[int] = []
    final_movers = list(movers)
    final_pos = current_pos
    for step_index in range(steps):
        new_progress = (npc_progress - 1) % track_length
        new_pos = new_progress
        destination_before = [runner for runner in grid.get(new_pos, []) if runner != NPC_ID]
        contact_cell.extend(destination_before)
        if skill_state is not None and skill_enabled(config, HIYUKI_ID) and HIYUKI_ID in progress:
            helpers.record_hiyuki_npc_path_contact(
                movers=[NPC_ID],
                progress=progress,
                track_length=track_length,
                path=(new_pos,),
                skill_state=skill_state,
                trace=trace,
            )

        for runner in movers:
            progress[runner] = new_progress
        moving_without_npc = [runner for runner in movers if runner != NPC_ID]
        if grid.get(new_pos):
            grid[new_pos] = moving_without_npc + [runner for runner in grid[new_pos] if runner != NPC_ID] + [NPC_ID]
        else:
            grid[new_pos] = moving_without_npc + [NPC_ID]
        keep_npc_rightmost(grid[new_pos])

        npc_progress = new_progress
        final_pos = new_pos
        final_movers = list(movers)
        path.append(new_pos)

        if step_index < steps - 1:
            current_cell = grid[new_pos]
            keep_npc_rightmost(current_cell)
            npc_idx = current_cell.index(NPC_ID)
            movers = current_cell[:npc_idx] + [NPC_ID]
            remaining = current_cell[npc_idx + 1 :]
            if remaining:
                grid[new_pos] = remaining
            else:
                grid.pop(new_pos, None)

    if trace:
        helpers.log_block(
            trace,
            "NPC行动：",
            f"后退步数：{steps}",
            f"路径：{' -> '.join(helpers.format_position(pos) for pos in path)}",
            f"接触角色：{helpers.format_cell(contact_cell)}",
            f"最终移动队列：{helpers.format_cell(final_movers)}",
            f"格内顺序：{helpers.format_cell(grid[final_pos])}",
        )
    helpers.apply_cell_effects(
        grid,
        progress,
        final_movers,
        final_pos,
        rng,
        config,
        active_player=NPC_ID,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
    )
    return progress[NPC_ID]


def settle_npc_end_of_round(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    runners: Sequence[int],
    npc_progress: int,
    track_length: int,
    trace: TraceContext,
    helpers: NPCHelpers,
) -> int:
    npc_pos = npc_progress % track_length
    last_runner = helpers.current_rank(runners, progress, grid)[-1]
    last_pos = display_position(progress[last_runner], track_length)
    if npc_pos >= last_pos:
        progress[NPC_ID] = npc_progress
        if trace:
            helpers.log_block(
                trace,
                "NPC停留：",
                f"原因：NPC位置不小于最后一名{helpers.format_runner(last_runner)}的位置",
                f"NPC位置：{helpers.format_position(npc_pos)}",
                f"最后一名位置：{helpers.format_position(last_pos)}",
            )
        return npc_progress
    remove_runner_from_grid(grid, NPC_ID)
    if grid.get(0):
        grid[0] = grid[0] + [NPC_ID]
    else:
        grid[0] = [NPC_ID]
    keep_npc_rightmost(grid[0])
    progress[NPC_ID] = 0
    if trace:
        helpers.log_block(
            trace,
            "NPC回到起始格：",
            "原因：NPC位置小于最后一名位置",
            f"NPC位置：{helpers.format_position(npc_pos)}",
            f"最后一名：{helpers.format_runner(last_runner)}",
            f"最后一名位置：{helpers.format_position(last_pos)}",
        )
    return 0
