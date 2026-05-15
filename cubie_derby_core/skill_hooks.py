from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from .movement import display_position, keep_npc_rightmost, remove_runner_from_grid
from .runners import AEMEATH_ID, HIYUKI_ID, JINHSI_ID, LUNO_ID, NPC_ID
from .skills import record_skill_success, skill_enabled, skill_enabled_from_set
from .tracing import TraceContext

AddGroupToPositionFn = Callable[..., None]
CurrentRankFn = Callable[[Sequence[int], dict[int, int], dict[int, Sequence[int]]], list[int]]
FormatCellFn = Callable[[Iterable[int]], str]
FormatPositionFn = Callable[[int], str]
FormatRunnerFn = Callable[[int], str]
TraceLogFn = Callable[..., None]


@dataclass(frozen=True)
class SkillHookHelpers:
    add_group_to_position: AddGroupToPositionFn
    current_rank: CurrentRankFn
    format_cell: FormatCellFn
    format_position: FormatPositionFn
    format_runner: FormatRunnerFn
    log_block: TraceLogFn
    log_timing: TraceLogFn


def nearest_runner_progress_ahead(
    *,
    progress: dict[int, int],
    from_progress: int,
    track_length: int,
    excluded: set[int],
) -> int | None:
    best: int | None = None
    for runner, runner_progress in progress.items():
        if runner <= 0 or runner in excluded or runner_progress <= from_progress or runner_progress >= track_length:
            continue
        if best is None or runner_progress < best:
            best = runner_progress
    return best


def gather_runners_to_luno_cell(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    ranking: Sequence[int],
    target_progress: int,
    track_length: int,
) -> None:
    target_pos = display_position(target_progress, track_length)
    npc_present = NPC_ID in grid.get(target_pos, [])
    for runner in ranking:
        remove_runner_from_grid(grid, runner)
    for runner in ranking:
        progress[runner] = target_progress
    grid[target_pos] = list(ranking) + ([NPC_ID] if npc_present else [])
    keep_npc_rightmost(grid[target_pos])


def maybe_trigger_aemeath_after_active_move(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    start_progress: int,
    action_had_forward_movement: bool,
    rng: random.Random,
    skill_state: Any | None,
    movement_state: Any | None = None,
    trace: TraceContext = False,
    helpers: SkillHookHelpers,
    aemeath_trigger_cell: int = 17,
) -> None:
    if (
        skill_state is None
        or not skill_state.aemeath_available
        or not skill_state.aemeath_ready
        or not skill_enabled(config, AEMEATH_ID)
        or AEMEATH_ID not in progress
        or not action_had_forward_movement
    ):
        return
    end_progress = progress[AEMEATH_ID]
    if end_progress >= config.track_length:
        return
    if trace:
        helpers.log_timing(trace, "行动结束", f"{helpers.format_runner(AEMEATH_ID)}检查前方是否存在其他非NPC角色")
    target_progress = nearest_runner_progress_ahead(
        progress=progress,
        from_progress=end_progress,
        track_length=config.track_length,
        excluded={AEMEATH_ID, NPC_ID},
    )
    if target_progress is None:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(AEMEATH_ID)}技能未触发：",
                "原因：当前前方没有其他非NPC角色",
                "效果：保留待判定状态，等待下次主动前进结束后继续检查",
            )
        return

    current_pos = display_position(end_progress, config.track_length)
    current_cell = grid.get(current_pos, [])
    if AEMEATH_ID in current_cell:
        current_cell[:] = [runner for runner in current_cell if runner != AEMEATH_ID]
        if current_cell:
            keep_npc_rightmost(current_cell)
        else:
            grid.pop(current_pos, None)

    skill_state.aemeath_available = False
    skill_state.aemeath_ready = False
    record_skill_success(skill_state, AEMEATH_ID)
    if trace:
        helpers.log_block(
            trace,
            f"{helpers.format_runner(AEMEATH_ID)}技能触发：",
            f"判定位置：{helpers.format_position(current_pos)}",
            f"传送目标：{helpers.format_position(display_position(target_progress, config.track_length))}",
            "效果：同行角色停留在原行动终点，爱弥斯单独传送到目标格最左侧",
        )
    helpers.add_group_to_position(
        grid,
        progress,
        [AEMEATH_ID],
        target_progress,
        rng,
        config,
        active_player=AEMEATH_ID,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
        apply_effects=False,
    )


def maybe_trigger_luno_after_action(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    skill_state: Any | None,
    trace: TraceContext = False,
    helpers: SkillHookHelpers,
    aemeath_trigger_cell: int = 17,
) -> None:
    if (
        skill_state is None
        or not skill_state.luno_available
        or not skill_enabled(config, LUNO_ID)
        or LUNO_ID not in progress
    ):
        return
    end_progress = progress[LUNO_ID]
    current_pos = display_position(end_progress, config.track_length)
    if trace:
        helpers.log_timing(trace, "行动结束", f"{helpers.format_runner(LUNO_ID)}检查自己是否已经经过第17格")
    if end_progress < aemeath_trigger_cell:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(LUNO_ID)}技能未触发：",
                f"原因：当前尚未经过{helpers.format_position(aemeath_trigger_cell)}",
                f"判定位置：{helpers.format_position(current_pos)}",
            )
        return

    ranking = helpers.current_rank(config.runners, progress, grid)
    luno_rank_index = ranking.index(LUNO_ID)
    if not (0 < luno_rank_index < len(ranking) - 1):
        if trace:
            reason = "去掉NPC后当前排名为第一名" if luno_rank_index == 0 else "去掉NPC后当前排名为最后一名"
            helpers.log_block(
                trace,
                f"{helpers.format_runner(LUNO_ID)}技能未触发：",
                f"原因：{reason}",
                "效果：保留技能，等待下次主动行动结束后继续判定",
                f"当前排名：{helpers.format_cell(ranking)}",
            )
        return

    skill_state.luno_available = False
    record_skill_success(skill_state, LUNO_ID)
    gather_runners_to_luno_cell(
        grid=grid,
        progress=progress,
        ranking=ranking,
        target_progress=end_progress,
        track_length=config.track_length,
    )
    if trace:
        helpers.log_block(
            trace,
            f"{helpers.format_runner(LUNO_ID)}技能触发：",
            f"判定位置：{helpers.format_position(current_pos)}",
            f"汇集顺序：{helpers.format_cell(ranking)}",
            f"格内顺序：{helpers.format_cell(grid[display_position(end_progress, config.track_length)])}",
        )


def record_hiyuki_npc_path_contact(
    *,
    movers: Sequence[int],
    progress: dict[int, int],
    track_length: int,
    path: Iterable[int],
    skill_state: Any | None,
    trace: TraceContext = False,
    helpers: SkillHookHelpers,
) -> None:
    if skill_state is None:
        return
    target_pos: int
    contact_kind: str
    if HIYUKI_ID in movers and NPC_ID in progress:
        target_pos = display_position(progress[NPC_ID], track_length)
        contact_kind = "hiyuki_to_npc"
    elif NPC_ID in movers and HIYUKI_ID in progress:
        target_pos = display_position(progress[HIYUKI_ID], track_length)
        contact_kind = "npc_to_hiyuki"
    else:
        return
    found = False
    for pos in path:
        if pos == target_pos:
            found = True
            break
    if not found:
        return
    if skill_state.hiyuki_bonus_steps > 0:
        if trace:
            if contact_kind == "hiyuki_to_npc":
                reason = f"{helpers.format_runner(HIYUKI_ID)}移动路径经过NPC所在{helpers.format_position(target_pos)}"
            else:
                reason = f"NPC移动路径经过{helpers.format_runner(HIYUKI_ID)}所在{helpers.format_position(target_pos)}"
            helpers.log_block(
                trace,
                f"{helpers.format_runner(HIYUKI_ID)}技能不重复叠加：",
                f"原因：{reason}",
                "当前状态：已生效",
            )
        return
    skill_state.hiyuki_bonus_steps += 1
    record_skill_success(skill_state, HIYUKI_ID)
    if trace:
        if contact_kind == "hiyuki_to_npc":
            reason = f"{helpers.format_runner(HIYUKI_ID)}移动路径经过NPC所在{helpers.format_position(target_pos)}"
        else:
            reason = f"NPC移动路径经过{helpers.format_runner(HIYUKI_ID)}所在{helpers.format_position(target_pos)}"
        helpers.log_block(
            trace,
            f"{helpers.format_runner(HIYUKI_ID)}技能触发：",
            f"原因：{reason}",
            "效果：之后移动额外+1步",
        )


def maybe_trigger_player1_skill_after_action(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    actor: int,
    track_length: int,
    rng: random.Random,
    disabled_skills: frozenset[int] = frozenset(),
    skill_state: Any | None = None,
    trace: TraceContext = False,
    helpers: SkillHookHelpers,
    jinhsi_reorder_chance: float = 0.4,
) -> None:
    if actor in (JINHSI_ID, NPC_ID) or JINHSI_ID not in progress or not skill_enabled_from_set(disabled_skills, JINHSI_ID):
        return
    if actor not in progress:
        return

    if trace:
        helpers.log_timing(
            trace,
            "行动结束",
            f"{helpers.format_runner(JINHSI_ID)}检查行动角色{helpers.format_runner(actor)}在本回合行动结算后是否位于自己紧邻左侧",
        )

    pos = display_position(progress[JINHSI_ID], track_length)
    actor_pos = display_position(progress[actor], track_length)
    if actor_pos != pos:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能不判定：",
                f"行动角色：{helpers.format_runner(actor)}",
                f"行动角色终点：{helpers.format_position(actor_pos)}",
                f"{helpers.format_runner(JINHSI_ID)}位置：{helpers.format_position(pos)}",
                "原因：行动角色终点未与自己同格",
            )
        return

    cell = grid.get(pos)
    if not cell or JINHSI_ID not in cell:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能不判定：",
                f"位置：{helpers.format_position(pos)}",
                f"原因：{helpers.format_runner(JINHSI_ID)}不在该格",
            )
        return

    keep_npc_rightmost(cell)
    one_idx = cell.index(JINHSI_ID)

    if actor not in cell or one_idx == 0 or cell[one_idx - 1] != actor:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能不判定：",
                f"行动角色：{helpers.format_runner(actor)}",
                f"位置：{helpers.format_position(pos)}",
                f"原因：行动角色不紧邻{helpers.format_runner(JINHSI_ID)}左侧",
                f"格内顺序：{helpers.format_cell(cell)}",
            )
        return

    left_runners = [actor]
    if not left_runners:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能不判定：",
                f"位置：{helpers.format_position(pos)}",
                "原因：左侧没有角色",
                f"格内顺序：{helpers.format_cell(cell)}",
            )
        return

    if trace:
        helpers.log_block(
            trace,
            f"{helpers.format_runner(JINHSI_ID)}技能进入概率判定：",
            f"左侧角色：{helpers.format_cell(left_runners)}",
            f"格内顺序：{helpers.format_cell(cell)}",
        )
    if rng.random() <= jinhsi_reorder_chance:
        cell[:] = [JINHSI_ID] + [runner for runner in cell if runner != JINHSI_ID]
        keep_npc_rightmost(cell)
        record_skill_success(skill_state, JINHSI_ID)
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能触发：",
                f"原左侧角色：{helpers.format_cell(left_runners)}",
                f"格内顺序：{helpers.format_cell(cell)}",
            )
    else:
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(JINHSI_ID)}技能未触发：",
                "原因：概率判定失败",
                f"格内顺序：{helpers.format_cell(cell)}",
            )
