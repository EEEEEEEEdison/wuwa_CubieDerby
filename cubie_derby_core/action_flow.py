from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .runners import AEMEATH_ID, CARTETHYIA_ID, LUNO_ID
from .skills import record_skill_success, skill_enabled
from .tracing import TraceContext

CurrentRankFn = Callable[[Sequence[int], dict[int, int], dict[int, Sequence[int]]], list[int]]
LogBlockFn = Callable[..., None]
LogRankDecisionFn = Callable[[TraceContext, Sequence[int], bool], None]
LogTimingFn = Callable[..., None]
MaybeTriggerAemeathFn = Callable[..., None]
MaybeTriggerLunoFn = Callable[..., None]
MaybeTriggerPlayer1Fn = Callable[..., None]
RankScopeFn = Callable[[Sequence[int], dict[int, int], bool], tuple[int, ...]]
FormatRunnerFn = Callable[[int], str]


@dataclass(frozen=True)
class PostActionHelpers:
    current_rank: CurrentRankFn
    format_runner: FormatRunnerFn
    log_block: LogBlockFn
    log_rank_decision: LogRankDecisionFn
    log_timing: LogTimingFn
    maybe_trigger_aemeath_after_active_move: MaybeTriggerAemeathFn
    maybe_trigger_luno_after_action: MaybeTriggerLunoFn
    maybe_trigger_player1_skill_after_action: MaybeTriggerPlayer1Fn
    rank_scope: RankScopeFn


@dataclass(frozen=True)
class PostActionState:
    new_progress: int
    cartethyia_available: bool
    cartethyia_extra_steps: bool


def resolve_post_action_effects(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    player: int,
    runners: Sequence[int],
    config: Any,
    npc_rank_active: bool,
    action_start_progress: int,
    total_steps: int,
    rng: random.Random,
    skill_state: Any | None,
    movement_state: Any | None = None,
    trace: TraceContext = False,
    cartethyia_available: bool,
    cartethyia_extra_steps: bool,
    helpers: PostActionHelpers,
) -> PostActionState:
    helpers.maybe_trigger_player1_skill_after_action(
        grid=grid,
        progress=progress,
        actor=player,
        track_length=config.track_length,
        rng=rng,
        disabled_skills=config.disabled_skills,
        skill_state=skill_state,
        trace=trace,
    )

    if player == AEMEATH_ID:
        helpers.maybe_trigger_aemeath_after_active_move(
            grid=grid,
            progress=progress,
            config=config,
            start_progress=action_start_progress,
            action_had_forward_movement=total_steps > 0,
            rng=rng,
            skill_state=skill_state,
            movement_state=movement_state,
            trace=trace,
        )

    if player == LUNO_ID:
        helpers.maybe_trigger_luno_after_action(
            grid=grid,
            progress=progress,
            config=config,
            skill_state=skill_state,
            trace=trace,
        )

    if player == CARTETHYIA_ID and skill_enabled(config, CARTETHYIA_ID) and cartethyia_available:
        if trace:
            helpers.log_timing(trace, "行动结束", f"{helpers.format_runner(player)}检查是否处于最后一名，以决定本场后续强化")
        rank_for_decision = helpers.current_rank(
            helpers.rank_scope(runners, progress, npc_rank_active),
            progress,
            grid,
        )
        helpers.log_rank_decision(trace, rank_for_decision, npc_rank_active)
        if rank_for_decision[-1] == player:
            cartethyia_extra_steps = True
            cartethyia_available = False
            record_skill_success(skill_state, player)
            if trace:
                helpers.log_block(
                    trace,
                    f"{helpers.format_runner(player)}技能进入强化状态：",
                    "效果：本场剩余回合可判定额外+2步",
                )
        elif trace:
            helpers.log_block(
                trace,
                f"{helpers.format_runner(player)}技能未进入强化状态：",
                "原因：行动结束后不是最后一名",
            )

    return PostActionState(
        new_progress=progress[player],
        cartethyia_available=cartethyia_available,
        cartethyia_extra_steps=cartethyia_extra_steps,
    )
