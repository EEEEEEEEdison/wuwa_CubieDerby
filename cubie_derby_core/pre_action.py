from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .runners import (
    AUGUSTA_ID,
    BRANT_ID,
    CALCHARO_ID,
    CAMELLYA_ID,
    CANTARELLA_ID,
    CARTETHYIA_ID,
    CHISA_ID,
    DENIA_ID,
    HIYUKI_ID,
    LYNAE_ID,
    NPC_ID,
    PHOEBE_ID,
    PHROLOVA_ID,
    POTATO_ID,
    ROCCIA_ID,
    ZANI_ID,
)
from .skills import (
    apply_chisa_bonus,
    apply_lynae_skill,
    apply_sigrika_debuff,
    check_denia_skill,
    check_hiyuki_bonus,
    record_skill_success,
    skill_enabled,
)
from .tracing import TraceContext

CurrentRankFn = Callable[[Sequence[int], dict[int, int], dict[int, Sequence[int]]], list[int]]
FormatCellFn = Callable[[Sequence[int]], str]
FormatRunnerFn = Callable[[int], str]
LogBlockFn = Callable[..., None]
LogRankDecisionFn = Callable[[TraceContext, Sequence[int], bool], None]
LogTimingFn = Callable[..., None]
RankScopeFn = Callable[[Sequence[int], dict[int, int], bool], tuple[int, ...]]


@dataclass(frozen=True)
class PreActionHelpers:
    current_rank: CurrentRankFn
    format_cell: FormatCellFn
    format_runner: FormatRunnerFn
    log_block: LogBlockFn
    log_rank_decision: LogRankDecisionFn
    log_timing: LogTimingFn
    rank_scope: RankScopeFn


@dataclass(frozen=True)
class PreActionResult:
    extra_steps: int
    total_steps: int
    skip_carried_runners: bool
    cantarella_move: bool
    augusta_skip_turn: bool
    zani_extra_steps: int


def resolve_pre_action_state(
    *,
    player: int,
    current_cell: Sequence[int],
    grid: dict[int, Sequence[int]],
    progress: dict[int, int],
    config: Any,
    runners: Sequence[int],
    player_order: Sequence[int],
    round_number: int,
    npc_rank_active: bool,
    dice: int,
    rng: random.Random,
    skill_state: Any,
    trace: TraceContext,
    chisa_bonus_active: bool,
    sigrika_debuffed: set[int],
    cantarella_state: int,
    zani_extra_steps: int,
    cartethyia_extra_steps: bool,
    helpers: PreActionHelpers,
    camellya_solo_action_chance: float,
    zani_extra_steps_chance: float,
    cartethyia_extra_steps_chance: float,
    phoebe_extra_step_chance: float,
    potato_repeat_dice_chance: float,
) -> PreActionResult:
    extra_steps = 0
    skip_carried_runners = False
    cantarella_move = False
    augusta_skip_turn = False

    if player == AUGUSTA_ID and skill_enabled(config, AUGUSTA_ID):
        non_npc_cell = [runner for runner in current_cell if runner != NPC_ID]
        if skill_state.augusta_force_last_next_round:
            skill_state.augusta_force_last_next_round = False
            if trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能本回合不判定：",
                    "原因：上一回合已触发停行动作",
                    "效果：本回合仅保留固定最后行动",
                )
        elif round_number == 1 and config.random_start_stack:
            if trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能本回合不判定：",
                    "原因：随机同格开局时，第一回合不发动技能",
                )
        else:
            if trace:
                helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查自己是否位于同格最左侧且同格存在其他角色")
            if len(non_npc_cell) > 1 and non_npc_cell[0] == player:
                augusta_skip_turn = True
                skill_state.augusta_force_last_next_round = True
                record_skill_success(skill_state, player)
                if trace:
                    helpers.log_block(
                        trace,
                        f"{helpers.format_runner(player)}技能触发：",
                        "原因：自己位于同格最左侧，且同格存在其他角色",
                        "效果：本回合不行动，下回合固定最后行动且不再判定自身技能",
                    )
            elif trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能未触发：",
                    "原因：当前不满足最左侧且同格有其他角色",
                    f"格内顺序：{helpers.format_cell(current_cell)}",
                )

    if player == DENIA_ID and skill_enabled(config, DENIA_ID):
        extra_steps += check_denia_skill(skill_state, dice, trace)
    if player == CHISA_ID and skill_enabled(config, CHISA_ID):
        extra_steps += apply_chisa_bonus(skill_state, chisa_bonus_active, trace)

    if player == CALCHARO_ID and skill_enabled(config, CALCHARO_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查是否为最后一名")
        rank_for_decision = helpers.current_rank(helpers.rank_scope(runners, progress, npc_rank_active), progress, grid)
        helpers.log_rank_decision(trace, rank_for_decision, npc_rank_active)
        if rank_for_decision[-1] == player:
            extra_steps = 3
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "原因：当前最后一名", "效果：额外+3步")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：当前不是最后一名")
    elif player == CAMELLYA_ID and skill_enabled(config, CAMELLYA_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}进行50%独自行动判定")
        if rng.random() <= camellya_solo_action_chance:
            extra_steps = len(current_cell) - 1
            skip_carried_runners = True
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：独自行动", f"额外步数：+{extra_steps}")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：50%判定失败")
    elif player == ROCCIA_ID and skill_enabled(config, ROCCIA_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查是否为本轮最后行动者")
        if player_order[-1] == player:
            extra_steps = 2
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "原因：本轮最后行动", "效果：额外+2步")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：不是本轮最后行动者")
    elif player == BRANT_ID and skill_enabled(config, BRANT_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查是否为本轮最先行动者")
        if player_order[0] == player:
            extra_steps = 2
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "原因：本轮最先行动", "效果：额外+2步")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：不是本轮最先行动者")
    elif player == CANTARELLA_ID and skill_enabled(config, CANTARELLA_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查是否处于逐格移动状态")
        cantarella_move = cantarella_state == 1
        if cantarella_move:
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能生效：", "效果：本次逐格移动")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未生效：", "原因：不处于逐格移动状态")
    elif player == ZANI_ID and skill_enabled(config, ZANI_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}先结算上次保留的额外步数，再检查同格触发")
        extra_steps = zani_extra_steps
        if len(current_cell) > 1 and rng.random() <= zani_extra_steps_chance:
            zani_extra_steps = 2
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：下一次行动额外+2步")
        else:
            zani_extra_steps = 0
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "效果：下一次行动无额外步数")
    elif player == CARTETHYIA_ID and skill_enabled(config, CARTETHYIA_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}若已进入强化状态，则检查60%额外+2步")
        if cartethyia_extra_steps and rng.random() <= cartethyia_extra_steps_chance:
            extra_steps = 2
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：额外+2步")
        elif cartethyia_extra_steps:
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：本次60%判定失败")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未判定：", "原因：尚未进入强化状态")
    elif player == PHOEBE_ID and skill_enabled(config, PHOEBE_ID):
        if trace:
            helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}进行50%额外+1步判定")
        if rng.random() <= phoebe_extra_step_chance:
            extra_steps = 1
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：额外+1步")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：50%判定失败")
    elif player == HIYUKI_ID and skill_enabled(config, HIYUKI_ID):
        extra_steps += check_hiyuki_bonus(skill_state, trace)

    total_steps = dice + extra_steps
    if player == POTATO_ID and skill_enabled(config, POTATO_ID):
        if trace:
            helpers.log_timing(trace, "骰子后", f"{helpers.format_runner(player)}进行重复本次骰子的判定")
        if rng.random() <= potato_repeat_dice_chance:
            total_steps += dice
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(trace, f"{helpers.format_runner(player)}技能触发：", "效果：重复本次骰子", f"总步数：{total_steps}")
        elif trace:
            helpers.log_block(trace, f"{helpers.format_runner(player)}技能未触发：", "原因：本次不重复骰子")

    if player == LYNAE_ID and skill_enabled(config, LYNAE_ID):
        total_steps, lynae_step_adjustment = apply_lynae_skill(
            skill_state,
            rng,
            dice=dice,
            total_steps=total_steps,
            trace=trace,
        )
        extra_steps += lynae_step_adjustment

    if player == PHROLOVA_ID and skill_enabled(config, PHROLOVA_ID):
        non_npc_cell = [runner for runner in current_cell if runner != NPC_ID]
        if round_number == 1 and config.random_start_stack:
            if trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能本回合不判定：",
                    "原因：随机同格开局时，第一回合不发动技能",
                )
        else:
            if trace:
                helpers.log_timing(trace, "行动开始", f"{helpers.format_runner(player)}检查自己是否位于同格最右侧且同格存在其他角色")
            if len(non_npc_cell) > 1 and non_npc_cell[-1] == player:
                extra_steps += 3
                total_steps += 3
                record_skill_success(skill_state, player)
                if trace:
                    helpers.log_block(
                        trace,
                        f"{helpers.format_runner(player)}技能触发：",
                        "原因：自己位于同格最右侧，且同格存在其他角色",
                        "效果：本回合额外前进3格",
                    )
            elif trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能未触发：",
                    "原因：当前不满足最右侧且同格有其他角色",
                    f"格内顺序：{helpers.format_cell(current_cell)}",
                )

    if augusta_skip_turn:
        total_steps = 0

    total_steps = apply_sigrika_debuff(
        player=player,
        total_steps=total_steps,
        debuffed=sigrika_debuffed,
        skill_state=skill_state,
        trace=trace,
    )

    return PreActionResult(
        extra_steps=extra_steps,
        total_steps=total_steps,
        skip_carried_runners=skip_carried_runners,
        cantarella_move=cantarella_move,
        augusta_skip_turn=augusta_skip_turn,
        zani_extra_steps=zani_extra_steps,
    )
