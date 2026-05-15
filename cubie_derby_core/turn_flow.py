from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .movement import display_position
from .tracing import TraceContext

ApplyShuffleCellEffectFn = Callable[..., None]
FormatCellFn = Callable[[Sequence[int]], str]
FormatPositionFn = Callable[[int], str]
FormatRunnerFn = Callable[[int], str]
LogFn = Callable[[TraceContext, str], None]
LogBlockFn = Callable[..., None]
LogGridFn = Callable[..., None]
LogTimingFn = Callable[..., None]
MoveCantarellaFn = Callable[..., tuple[int, int, list[int]]]
MoveRunnerWithLeftSideFn = Callable[..., int]
MoveSingleRunnerFn = Callable[..., int]
ResolvePostActionFn = Callable[..., Any]
ResolvePreActionFn = Callable[..., Any]


@dataclass(frozen=True)
class TurnFlowHelpers:
    apply_shuffle_cell_effect: ApplyShuffleCellEffectFn
    format_cell: FormatCellFn
    format_position: FormatPositionFn
    format_runner: FormatRunnerFn
    log: LogFn
    log_block: LogBlockFn
    log_grid: LogGridFn
    log_timing: LogTimingFn
    move_cantarella: MoveCantarellaFn
    move_runner_with_left_side: MoveRunnerWithLeftSideFn
    move_single_runner: MoveSingleRunnerFn
    resolve_post_action_effects: ResolvePostActionFn
    resolve_pre_action_state: ResolvePreActionFn


@dataclass(frozen=True)
class TurnFlowResult:
    finished: bool
    new_progress: int
    cantarella_state: int
    cantarella_group: list[int]
    zani_extra_steps: int
    cartethyia_available: bool
    cartethyia_extra_steps: bool


def execute_player_turn(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: Any,
    runners: Sequence[int],
    player_order: Sequence[int],
    player: int,
    round_number: int,
    npc_rank_active: bool,
    round_dice: dict[int, int],
    rng: random.Random,
    skill_state: Any,
    movement_state: Any,
    trace: TraceContext,
    track_length: int,
    chisa_bonus_active: bool,
    sigrika_debuffed: set[int],
    cantarella_state: int,
    cantarella_group: list[int],
    zani_extra_steps: int,
    cartethyia_available: bool,
    cartethyia_extra_steps: bool,
    helpers: TurnFlowHelpers,
) -> TurnFlowResult:
    action_start_progress = progress[player]
    current_pos = display_position(action_start_progress, track_length)
    current_cell = grid[current_pos]
    if player not in current_cell:
        raise RuntimeError(f"runner {player} is missing from position {current_pos}")
    idx_in_cell = current_cell.index(player)

    if trace:
        helpers.log(trace, f"--- {helpers.format_runner(player)}行动 ---")
        helpers.log_block(
            trace,
            "行动开始：",
            f"角色：{helpers.format_runner(player)}",
            f"位置：{helpers.format_position(current_pos)}",
            f"格内顺序：{helpers.format_cell(current_cell)}",
        )

    dice = round_dice[player]
    pre_action = helpers.resolve_pre_action_state(
        player=player,
        current_cell=current_cell,
        grid=grid,
        progress=progress,
        config=config,
        runners=runners,
        player_order=player_order,
        round_number=round_number,
        npc_rank_active=npc_rank_active,
        dice=dice,
        rng=rng,
        skill_state=skill_state,
        trace=trace,
        chisa_bonus_active=chisa_bonus_active,
        sigrika_debuffed=sigrika_debuffed,
        cantarella_state=cantarella_state,
        zani_extra_steps=zani_extra_steps,
        cartethyia_extra_steps=cartethyia_extra_steps,
    )
    extra_steps = pre_action.extra_steps
    total_steps = pre_action.total_steps
    skip_carried_runners = pre_action.skip_carried_runners
    cantarella_move = pre_action.cantarella_move
    zani_extra_steps = pre_action.zani_extra_steps

    if trace:
        helpers.log_block(
            trace,
            f"{helpers.format_runner(player)}掷骰结果：",
            f"骰子：{dice}",
            f"额外步数：{extra_steps}",
            f"总步数：{total_steps}",
        )

    if total_steps <= 0:
        new_progress = progress[player]
        current_pos = display_position(new_progress, track_length)
        if trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(player)}本回合无法移动：",
                "移动结算：视为主动移动0格，原地停留",
                "后续：若当前停留格是打乱格，则触发打乱效果；随后仍按行动结束后的最终站位结算今汐技能判定",
            )
        if current_pos in config.shuffle_cells:
            if trace:
                helpers.log_timing(trace, "行动结束", f"检查{helpers.format_position(current_pos)}是否为打乱顺序格")
            helpers.apply_shuffle_cell_effect(grid, current_pos, rng, trace=trace)
        new_progress = progress[player]
    elif cantarella_move:
        new_progress, cantarella_state, cantarella_group = helpers.move_cantarella(
            grid=grid,
            progress=progress,
            config=config,
            player=player,
            total_steps=total_steps,
            rng=rng,
            cantarella_state=cantarella_state,
            cantarella_group=cantarella_group,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )
    elif skip_carried_runners:
        new_progress = helpers.move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=player,
            total_steps=total_steps,
            rng=rng,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )
    else:
        new_progress = helpers.move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=player,
            idx_in_cell=idx_in_cell,
            total_steps=total_steps,
            rng=rng,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )

    if new_progress >= track_length:
        if trace:
            helpers.log_grid(trace, grid, title="行动后位置分布：")
            helpers.log_timing(trace, "移动结算后", "到达或经过终点，立即进行冠军判定")
        return TurnFlowResult(
            finished=True,
            new_progress=new_progress,
            cantarella_state=cantarella_state,
            cantarella_group=cantarella_group,
            zani_extra_steps=zani_extra_steps,
            cartethyia_available=cartethyia_available,
            cartethyia_extra_steps=cartethyia_extra_steps,
        )

    post_action_state = helpers.resolve_post_action_effects(
        grid=grid,
        progress=progress,
        player=player,
        runners=runners,
        config=config,
        npc_rank_active=npc_rank_active,
        action_start_progress=action_start_progress,
        total_steps=total_steps,
        rng=rng,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
        cartethyia_available=cartethyia_available,
        cartethyia_extra_steps=cartethyia_extra_steps,
    )
    new_progress = post_action_state.new_progress
    cartethyia_available = post_action_state.cartethyia_available
    cartethyia_extra_steps = post_action_state.cartethyia_extra_steps

    if trace:
        helpers.log_grid(trace, grid, title="行动后位置分布：")

    return TurnFlowResult(
        finished=False,
        new_progress=new_progress,
        cantarella_state=cantarella_state,
        cantarella_group=cantarella_group,
        zani_extra_steps=zani_extra_steps,
        cartethyia_available=cartethyia_available,
        cartethyia_extra_steps=cartethyia_extra_steps,
    )
