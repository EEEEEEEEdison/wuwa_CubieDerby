from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .runners import AUGUSTA_ID, CHANGLI_ID, CHISA_ID, NPC_ID
from .tracing import TraceContext

AddNPCToStartFn = Callable[[dict[int, list[int]]], None]
CheckPlayer2SkillFn = Callable[..., bool]
ChisaLowestDiceFn = Callable[[int, dict[int, int]], bool]
FormatPositionFn = Callable[[int], str]
FormatRoundDiceFn = Callable[[dict[int, int], Sequence[int]], str]
FormatRunnerArrowListFn = Callable[[Sequence[int]], str]
FormatRunnerFn = Callable[[int], str]
LogFn = Callable[[TraceContext, str], None]
LogBlockFn = Callable[..., None]
LogGridFn = Callable[..., None]
LogTimingFn = Callable[..., None]
LogChisaRoundCheckFn = Callable[..., None]
MarkSigrikaDebuffsFn = Callable[..., set[int]]
NextRoundActionOrderFn = Callable[..., list[int]]
RollRoundDiceFn = Callable[..., dict[int, int]]
SettleNpcEndOfRoundFn = Callable[..., int]
SkillEnabledFn = Callable[[Any, int], bool]


@dataclass(frozen=True)
class RoundFlowHelpers:
    add_npc_to_start: AddNPCToStartFn
    check_player2_skill: CheckPlayer2SkillFn
    chisa_has_lowest_dice: ChisaLowestDiceFn
    format_position: FormatPositionFn
    format_round_dice: FormatRoundDiceFn
    format_runner: FormatRunnerFn
    format_runner_arrow_list: FormatRunnerArrowListFn
    log: LogFn
    log_block: LogBlockFn
    log_chisa_round_check: LogChisaRoundCheckFn
    log_grid: LogGridFn
    log_timing: LogTimingFn
    mark_sigrika_debuffs: MarkSigrikaDebuffsFn
    next_round_action_order: NextRoundActionOrderFn
    roll_round_dice: RollRoundDiceFn
    settle_npc_end_of_round: SettleNpcEndOfRoundFn
    skill_enabled: SkillEnabledFn


@dataclass(frozen=True)
class RoundStartState:
    npc_active: bool
    npc_progress: int
    npc_rank_active: bool
    sigrika_debuffed: set[int]
    round_dice: dict[int, int]
    chisa_bonus_active: bool


@dataclass(frozen=True)
class RoundEndState:
    npc_progress: int
    player_order: list[int]
    cantarella_state: int


def prepare_round(
    *,
    config: Any,
    runners: Sequence[int],
    grid: dict[int, list[int]],
    progress: dict[int, int],
    player_order: Sequence[int],
    round_number: int,
    npc_active: bool,
    npc_progress: int,
    skill_state: Any,
    rng: random.Random,
    trace: TraceContext,
    helpers: RoundFlowHelpers,
) -> RoundStartState:
    npc_rank_active = False
    if config.npc_enabled and round_number >= config.npc_start_round and not npc_active:
        npc_active = True
        npc_progress = 0
        helpers.add_npc_to_start(grid)
        progress[NPC_ID] = npc_progress
        if trace:
            helpers.log_block(trace, "NPC登场：", f"出发位置：{helpers.format_position(0)}")

    if trace:
        helpers.log(trace, f"\n=== 第{round_number}轮 ===")
        helpers.log_grid(trace, grid, title="本轮开始时位置分布：")
    if trace and npc_active:
        helpers.log_block(trace, "NPC状态：", f"当前位置：{helpers.format_position(npc_progress % config.track_length)}")

    sigrika_debuffed = helpers.mark_sigrika_debuffs(
        runners=runners,
        progress=progress,
        grid=grid,
        round_number=round_number,
        skip_first_round=config.random_start_stack,
        disabled_skills=config.disabled_skills,
        trace=trace,
    )
    round_dice = helpers.roll_round_dice(player_order, rng, config=config, skill_state=skill_state)
    chisa_bonus_active = (
        CHISA_ID in player_order
        and helpers.skill_enabled(config, CHISA_ID)
        and helpers.chisa_has_lowest_dice(round_dice[CHISA_ID], round_dice)
    )
    if trace:
        helpers.log_block(trace, "本轮行动顺序：", helpers.format_runner_arrow_list(player_order))
        helpers.log_block(trace, "本轮骰点：", helpers.format_round_dice(round_dice, player_order))
        if CHISA_ID in player_order and helpers.skill_enabled(config, CHISA_ID):
            helpers.log_chisa_round_check(round_dice[CHISA_ID], round_dice, chisa_bonus_active, trace)

    return RoundStartState(
        npc_active=npc_active,
        npc_progress=npc_progress,
        npc_rank_active=npc_rank_active,
        sigrika_debuffed=sigrika_debuffed,
        round_dice=round_dice,
        chisa_bonus_active=chisa_bonus_active,
    )


def finalize_round(
    *,
    config: Any,
    runners: Sequence[int],
    grid: dict[int, list[int]],
    progress: dict[int, int],
    npc_active: bool,
    npc_progress: int,
    round_number: int,
    player_order: Sequence[int],
    rng: random.Random,
    trace: TraceContext,
    skill_state: Any,
    cantarella_state: int,
    helpers: RoundFlowHelpers,
) -> RoundEndState:
    if npc_active:
        if trace:
            helpers.log(trace, "")
            helpers.log_timing(trace, "回合结束", "NPC检查自身位置是否小于最后一名位置，若小于则回到第0格")
        npc_progress = helpers.settle_npc_end_of_round(
            grid=grid,
            progress=progress,
            runners=runners,
            npc_progress=npc_progress,
            track_length=config.track_length,
            trace=trace,
        )

    if CHANGLI_ID in runners:
        if trace:
            helpers.log(trace, "")
            helpers.log_timing(trace, "回合结束", f"{helpers.format_runner(CHANGLI_ID)}检查是否在同格最右侧之外，以决定下一轮是否最后行动")
        next_turn_last = helpers.check_player2_skill(
            grid,
            rng,
            disabled_skills=config.disabled_skills,
            skill_state=skill_state,
            trace=trace,
        )
    else:
        next_turn_last = False

    forced_last_runners: list[int] = []
    if skill_state.augusta_force_last_next_round and AUGUSTA_ID in runners:
        forced_last_runners.append(AUGUSTA_ID)
    if next_turn_last and CHANGLI_ID in runners:
        forced_last_runners.append(CHANGLI_ID)

    next_player_order = helpers.next_round_action_order(
        runners=runners,
        rng=rng,
        include_npc=config.npc_enabled and round_number + 1 >= config.npc_start_round,
        forced_last_runners=tuple(forced_last_runners),
    )

    if cantarella_state == 2:
        cantarella_state = 0

    return RoundEndState(
        npc_progress=npc_progress,
        player_order=next_player_order,
        cantarella_state=cantarella_state,
    )
