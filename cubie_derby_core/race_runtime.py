from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .runners import NPC_ID
from .tracing import TraceContext

AddNPCToStartFn = Callable[[dict[int, list[int]]], None]
CurrentRankFn = Callable[[Sequence[int], dict[int, int], dict[int, Sequence[int]]], list[int]]
FormatPositionListFn = Callable[[Iterable[int]], str]
FormatRunnerFn = Callable[[int], str]
FormatRunnerListFn = Callable[[Iterable[int]], str]
InitialPlayerOrderFn = Callable[[Any, dict[int, Sequence[int]], random.Random], list[int]]
LogBlockFn = Callable[..., None]
LogFn = Callable[[TraceContext, str], None]
MovementStateFactory = Callable[[], Any]
RaceResultFactory = Callable[..., Any]
SkillStateFactory = Callable[[], Any]
ValidatePositionsFn = Callable[[Sequence[int], dict[int, int]], None]
ValidateStartPositionFn = Callable[[int, int], None]


@dataclass
class RaceRuntimeState:
    grid: dict[int, list[int]]
    progress: dict[int, int]
    player_order: list[int]
    cantarella_state: int = 1
    cantarella_group: list[int] = field(default_factory=list)
    zani_extra_steps: int = 0
    cartethyia_available: bool = True
    cartethyia_extra_steps: bool = False
    skill_state: Any = None
    movement_state: Any = None
    npc_progress: int = 0
    npc_active: bool = False
    npc_rank_active: bool = False
    round_number: int = 1


def initialize_race_runtime(
    *,
    config: Any,
    rng: random.Random,
    trace: TraceContext,
    add_npc_to_start_fn: AddNPCToStartFn,
    format_position_list_fn: FormatPositionListFn,
    initial_player_order_fn: InitialPlayerOrderFn,
    log_block_fn: LogBlockFn,
    movement_state_factory: MovementStateFactory,
    skill_state_factory: SkillStateFactory,
    validate_positions_fn: ValidatePositionsFn,
    validate_start_position_fn: ValidateStartPositionFn,
) -> RaceRuntimeState:
    runners = config.runners
    track_length = config.track_length
    grid = {pos: list(cell) for pos, cell in config.start_grid.items() if cell}

    if config.random_start_stack:
        validate_start_position_fn(config.random_start_position, track_length)
        start_stack = list(runners)
        rng.shuffle(start_stack)
        grid = {config.random_start_position: start_stack}
    if config.npc_enabled:
        add_npc_to_start_fn(grid)

    progress: dict[int, int] = {}
    for pos, cell in grid.items():
        for runner in cell:
            if runner == NPC_ID:
                continue
            progress[runner] = pos
    validate_positions_fn(runners, progress)

    player_order = initial_player_order_fn(config, grid, rng)
    runtime = RaceRuntimeState(
        grid=grid,
        progress=progress,
        player_order=player_order,
        skill_state=skill_state_factory(),
        movement_state=movement_state_factory(),
    )

    if trace:
        log_block_fn(
            trace,
            "模拟配置：",
            f"赛制：{config.name}",
            f"赛季：{config.season}",
            f"环形赛道：{track_length}格",
        )
        log_block_fn(
            trace,
            "特殊格：",
            f"前进一格：{format_position_list_fn(sorted(config.forward_cells))}",
            f"后退一格：{format_position_list_fn(sorted(config.backward_cells))}",
            f"随机打乱：{format_position_list_fn(sorted(config.shuffle_cells))}",
            f"NPC：{'开启' if config.npc_enabled else '关闭'}",
        )
    return runtime


def build_race_result(
    *,
    config: Any,
    runners: Sequence[int],
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movement_state: Any,
    skill_state: Any,
    trace: TraceContext,
    current_rank_fn: CurrentRankFn,
    format_runner_fn: FormatRunnerFn,
    format_runner_list_fn: FormatRunnerListFn,
    log_block_fn: LogBlockFn,
    log_fn: LogFn,
    race_result_factory: RaceResultFactory,
) -> Any:
    ranking = current_rank_fn(runners, progress, grid)
    second_position = progress[ranking[1]] if len(ranking) > 1 else config.track_length
    winner = grid[0][0]
    result = race_result_factory(
        winner=winner,
        ranking=tuple(ranking),
        second_position=second_position,
        winner_margin=max(0, config.track_length - second_position),
        winner_carried_steps=movement_state.carried_steps.get(winner, 0),
        winner_total_steps=movement_state.total_steps.get(winner, 0),
        movement_stats=tuple(
            (runner, movement_state.total_steps.get(runner, 0), movement_state.carried_steps.get(runner, 0))
            for runner in runners
        ),
        skill_success_counts=tuple(sorted(skill_state.success_counts.items())),
    )
    if trace:
        log_fn(trace, "比赛结束：")
        log_block_fn(
            trace,
            "结果：",
            f"冠军：{format_runner_fn(result.winner)}",
            f"排名：{format_runner_list_fn(result.ranking)}",
            f"领先距离：{result.winner_margin}",
        )
    return result
