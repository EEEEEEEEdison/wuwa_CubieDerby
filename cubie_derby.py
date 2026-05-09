from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


MIN_START_POSITION = -3
DEFAULT_LAP_LENGTH = 24
SEASON2_LAP_LENGTH = 32
NPC_ID = -1
SIGRIKA_ID = 13
LUUK_HERSSEN_ID = 14
DENIA_ID = 15
HIYUKI_ID = 16
SEASON2_FORWARD_CELLS = frozenset({3, 11, 16, 23})
SEASON2_BACKWARD_CELLS = frozenset({10, 28})
SEASON2_SHUFFLE_CELLS = frozenset({6, 20})


RUNNER_NAMES: dict[int, str] = {
    1: "今汐",
    2: "长离",
    3: "卡卡罗",
    4: "守岸人",
    5: "椿",
    6: "小土豆",
    7: "洛可可",
    8: "布兰特",
    9: "坎特蕾拉",
    10: "赞妮",
    11: "卡提希娅",
    12: "菲比",
    SIGRIKA_ID: "西格莉卡",
    LUUK_HERSSEN_ID: "陆赫斯",
    DENIA_ID: "达尼娅",
    HIYUKI_ID: "绯雪",
}

RUNNER_ALIASES: dict[str, int] = {
    "jinhsi": 1,
    "changli": 2,
    "calcharo": 3,
    "shorekeeper": 4,
    "camellya": 5,
    "potato": 6,
    "roccia": 7,
    "brant": 8,
    "cantarella": 9,
    "zani": 10,
    "cartethyia": 11,
    "phoebe": 12,
    "sigrika": SIGRIKA_ID,
    "luuk": LUUK_HERSSEN_ID,
    "luuk herssen": LUUK_HERSSEN_ID,
    "luuk-herssen": LUUK_HERSSEN_ID,
    "luuk_herssen": LUUK_HERSSEN_ID,
    "luukherssen": LUUK_HERSSEN_ID,
    "denia": DENIA_ID,
    "hiyuki": HIYUKI_ID,
}

NAME_TO_RUNNER: dict[str, int] = {name: runner for runner, name in RUNNER_NAMES.items()}


@dataclass(frozen=True)
class RaceConfig:
    runners: tuple[int, ...]
    track_length: int
    start_grid: dict[int, tuple[int, ...]]
    season: int = 1
    forward_cells: frozenset[int] = field(default_factory=frozenset)
    backward_cells: frozenset[int] = field(default_factory=frozenset)
    shuffle_cells: frozenset[int] = field(default_factory=frozenset)
    npc_enabled: bool = False
    npc_start_round: int = 3
    random_start_stack: bool = False
    random_start_position: int = 0
    initial_order_mode: str = "random"  # random, start, fixed
    fixed_initial_order: tuple[int, ...] = ()
    name: str = "custom"


@dataclass(frozen=True)
class RaceResult:
    winner: int
    ranking: tuple[int, ...]
    second_position: int
    winner_margin: int


@dataclass
class RaceSkillState:
    hiyuki_bonus_steps: int = 0
    denia_last_dice: int | None = None


class TraceLogger:
    def __init__(self, echo: bool = False) -> None:
        self.echo = echo
        self.lines: list[str] = []

    def write_line(self, message: str) -> None:
        self.lines.append(message)
        if self.echo:
            print(message)

    def text(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")


@dataclass(frozen=True)
class RunnerSummary:
    runner: int
    name: str
    wins: int
    win_rate: float
    average_rank: float
    rank_variance: float
    winner_gap_per_race: float
    average_winning_margin: float


@dataclass(frozen=True)
class SimulationSummary:
    iterations: int
    config: RaceConfig
    rows: tuple[RunnerSummary, ...]

    @property
    def best(self) -> RunnerSummary:
        return max(self.rows, key=lambda row: (row.win_rate, -row.average_rank))


class MonteCarloAccumulator:
    def __init__(self, runners: Sequence[int]) -> None:
        self.runners = tuple(runners)
        self.index = {runner: i for i, runner in enumerate(self.runners)}
        size = len(self.runners)
        self.iterations = 0
        self.wins = [0] * size
        self.rank_sum = [0.0] * size
        self.rank_square_sum = [0.0] * size
        self.winner_gap_sum = [0.0] * size

    def add(self, result: RaceResult) -> None:
        self.iterations += 1
        winner_idx = self.index[result.winner]
        self.wins[winner_idx] += 1
        self.winner_gap_sum[winner_idx] += result.winner_margin
        for rank, runner in enumerate(result.ranking, start=1):
            idx = self.index[runner]
            self.rank_sum[idx] += rank
            self.rank_square_sum[idx] += rank * rank

    def merge(self, other: "MonteCarloAccumulator") -> None:
        if self.runners != other.runners:
            raise ValueError("cannot merge accumulators for different runner sets")
        self.iterations += other.iterations
        for i in range(len(self.runners)):
            self.wins[i] += other.wins[i]
            self.rank_sum[i] += other.rank_sum[i]
            self.rank_square_sum[i] += other.rank_square_sum[i]
            self.winner_gap_sum[i] += other.winner_gap_sum[i]

    def to_summary(self, config: RaceConfig) -> SimulationSummary:
        rows: list[RunnerSummary] = []
        n = self.iterations
        for runner in self.runners:
            idx = self.index[runner]
            wins = self.wins[idx]
            avg_rank = self.rank_sum[idx] / n if n else math.nan
            if n > 1:
                variance = (self.rank_square_sum[idx] - (self.rank_sum[idx] ** 2) / n) / (n - 1)
                variance = max(0.0, variance)
            else:
                variance = 0.0
            rows.append(
                RunnerSummary(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    wins=wins,
                    win_rate=wins / n if n else 0.0,
                    average_rank=avg_rank,
                    rank_variance=variance,
                    winner_gap_per_race=self.winner_gap_sum[idx] / n if n else 0.0,
                    average_winning_margin=self.winner_gap_sum[idx] / wins if wins else 0.0,
                )
            )
        return SimulationSummary(iterations=n, config=config, rows=tuple(rows))


def preset_config(mode: int, runners: Sequence[int] | None = None) -> RaceConfig:
    if mode == 1:
        selected = tuple(runners or (1, 2, 3, 4, 5, 6))
        return RaceConfig(
            runners=selected,
            track_length=DEFAULT_LAP_LENGTH,
            start_grid=empty_grid(DEFAULT_LAP_LENGTH),
            random_start_stack=True,
            initial_order_mode="start",
            name="mode1_random_order_random_start",
        )
    if mode == 2:
        selected = tuple(runners or (1, 2, 3, 4, 5, 6))
        return RaceConfig(
            runners=selected,
            track_length=DEFAULT_LAP_LENGTH,
            start_grid=empty_grid(DEFAULT_LAP_LENGTH),
            random_start_stack=True,
            initial_order_mode="start",
            name="mode2_start_order_random_start",
        )
    if mode == 3:
        selected = tuple(runners or (9, 10, 7, 12, 8, 11))
        start = {0: (9, 10, 7, 12, 8, 11)}
        return fixed_grid_config(
            name="mode3_fixed_order_fixed_start",
            runners=selected,
            track_length=DEFAULT_LAP_LENGTH,
            start_cells=start,
            initial_order=(9, 10, 7, 12, 8, 11),
        )
    if mode == 4:
        selected = tuple(runners or (3, 4, 8, 10))
        start = {1: (10,), 2: (4, 3), 3: (8,)}
        return fixed_grid_config(
            name="mode4_random_order_fixed_start",
            runners=selected,
            track_length=DEFAULT_LAP_LENGTH,
            start_cells=start,
            initial_order=None,
        )
    if mode == 5:
        selected = tuple(runners or (7, 8, 9, 10, 11, 12))
        start = {1: (10, 7, 9), 2: (12,), 3: (8, 11)}
        return fixed_grid_config(
            name="mode5_fixed_order_fixed_start",
            runners=selected,
            track_length=DEFAULT_LAP_LENGTH,
            start_cells=start,
            initial_order=(9, 8, 11, 7, 10, 12),
        )
    raise ValueError(f"unknown preset mode: {mode}")


def season_rules(season: int) -> dict[str, object]:
    if season == 1:
        return {
            "track_length": DEFAULT_LAP_LENGTH,
            "forward_cells": frozenset(),
            "backward_cells": frozenset(),
            "shuffle_cells": frozenset(),
            "npc_enabled": False,
        }
    if season == 2:
        return {
            "track_length": SEASON2_LAP_LENGTH,
            "forward_cells": SEASON2_FORWARD_CELLS,
            "backward_cells": SEASON2_BACKWARD_CELLS,
            "shuffle_cells": SEASON2_SHUFFLE_CELLS,
            "npc_enabled": True,
        }
    raise ValueError(f"unknown season: {season}")


def apply_season_rules(config: RaceConfig, season: int, track_length: int | None = None) -> RaceConfig:
    rules = season_rules(season)
    lap_length = track_length or int(rules["track_length"])
    validate_track_length(lap_length)
    for pos in config.start_grid:
        validate_start_position(pos, lap_length)
    validate_start_position(config.random_start_position, lap_length)
    return RaceConfig(
        runners=config.runners,
        track_length=lap_length,
        start_grid=config.start_grid,
        season=season,
        forward_cells=rules["forward_cells"],
        backward_cells=rules["backward_cells"],
        shuffle_cells=rules["shuffle_cells"],
        npc_enabled=bool(rules["npc_enabled"]),
        npc_start_round=config.npc_start_round,
        random_start_stack=config.random_start_stack,
        random_start_position=config.random_start_position,
        initial_order_mode=config.initial_order_mode,
        fixed_initial_order=config.fixed_initial_order,
        name=config.name,
    )


def empty_grid(track_length: int) -> dict[int, tuple[int, ...]]:
    validate_track_length(track_length)
    return {}


def fixed_grid_config(
    *,
    name: str,
    runners: Sequence[int],
    track_length: int,
    start_cells: dict[int, Sequence[int]],
    initial_order: Sequence[int] | None,
) -> RaceConfig:
    selected = tuple(runners)
    selected_set = set(selected)
    filtered_cells: dict[int, tuple[int, ...]] = {}
    for pos, cell in start_cells.items():
        filtered = tuple(runner for runner in cell if runner in selected_set)
        if filtered:
            filtered_cells[pos] = filtered
    grid = make_start_grid(track_length, filtered_cells)
    validate_fixed_start(selected, grid)
    if initial_order is None:
        mode = "random"
        fixed_order: tuple[int, ...] = ()
    else:
        mode = "fixed"
        fixed_order = tuple(runner for runner in initial_order if runner in selected_set)
        validate_same_runners(selected, fixed_order, "fixed initial order")
    return RaceConfig(
        runners=selected,
        track_length=track_length,
        start_grid=grid,
        random_start_stack=False,
        initial_order_mode=mode,
        fixed_initial_order=fixed_order,
        name=name,
    )


def validate_track_length(track_length: int) -> None:
    if track_length <= 0:
        raise ValueError("track_length must be positive")


def validate_start_position(pos: int, track_length: int) -> None:
    if pos < MIN_START_POSITION or pos >= track_length:
        raise ValueError(
            f"start position {pos} is outside the track; "
            f"expected {MIN_START_POSITION}..{track_length - 1}"
        )


def display_position(progress: int, track_length: int) -> int:
    return progress if progress < 0 else progress % track_length


def make_start_grid(track_length: int, cells: dict[int, Sequence[int]]) -> dict[int, tuple[int, ...]]:
    validate_track_length(track_length)
    grid: dict[int, tuple[int, ...]] = {}
    seen: set[int] = set()
    for pos, runners in cells.items():
        validate_start_position(pos, track_length)
        cell = tuple(runners)
        for runner in cell:
            if runner in seen:
                raise ValueError(f"runner {runner} appears more than once in start grid")
            seen.add(runner)
        if cell:
            grid[pos] = cell
    return grid


def validate_fixed_start(runners: Sequence[int], grid: dict[int, Sequence[int]]) -> None:
    seen = tuple(runner for _, cell in sorted(grid.items()) for runner in cell)
    validate_same_runners(runners, seen, "start grid")


def validate_same_runners(expected: Sequence[int], actual: Sequence[int], label: str) -> None:
    expected_set = set(expected)
    actual_set = set(actual)
    missing = expected_set - actual_set
    extra = actual_set - expected_set
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing runners: {format_runner_list(sorted(missing))}")
        if extra:
            parts.append(f"extra runners: {format_runner_list(sorted(extra))}")
        raise ValueError(f"{label} does not match selected runners ({'; '.join(parts)})")


def simulate_race(config: RaceConfig, rng: random.Random, trace: bool | TraceLogger = False) -> RaceResult:
    runners = config.runners
    track_length = config.track_length
    grid = {pos: list(cell) for pos, cell in config.start_grid.items() if cell}

    if config.random_start_stack:
        validate_start_position(config.random_start_position, track_length)
        start_stack = list(runners)
        rng.shuffle(start_stack)
        grid = {config.random_start_position: start_stack}

    progress: dict[int, int] = {}
    for pos, cell in grid.items():
        for runner in cell:
            progress[runner] = pos
    validate_positions(runners, progress)

    player_order = initial_player_order(config, grid, rng)
    cantarella_state = 1
    cantarella_group: list[int] = []
    zani_extra_steps = 0
    cartethyia_available = True
    cartethyia_extra_steps = False
    skill_state = RaceSkillState()
    npc_progress = 0
    npc_active = False
    npc_rank_active = False

    round_number = 1
    log_block(
        trace,
        "模拟配置：",
        f"赛制：{config.name}",
        f"赛季：{config.season}",
        f"环形赛道：{track_length}格",
    )
    log_block(
        trace,
        "特殊格：",
        f"前进一格：{format_position_list(sorted(config.forward_cells))}",
        f"后退一格：{format_position_list(sorted(config.backward_cells))}",
        f"随机打乱：{format_position_list(sorted(config.shuffle_cells))}",
        f"NPC：{'开启' if config.npc_enabled else '关闭'}",
    )
    while True:
        npc_rank_active = False
        if config.npc_enabled and round_number >= config.npc_start_round and not npc_active:
            npc_active = True
            npc_progress = 0
            add_npc_to_start(grid)
            progress[NPC_ID] = npc_progress
            log_block(trace, "NPC登场：", f"出发位置：{format_position(0)}")

        log(trace, f"\n=== 第{round_number}轮 ===")
        log_grid(trace, grid, title="本轮开始时位置分布：")
        if npc_active:
            log_block(trace, "NPC状态：", f"当前位置：{format_position(display_position(npc_progress, track_length))}")
        sigrika_debuffed = mark_sigrika_debuffs(
            runners=runners,
            progress=progress,
            grid=grid,
            round_number=round_number,
            trace=trace,
        )
        log_block(trace, "本轮行动顺序：", format_runner_arrow_list(player_order))

        finished = False
        for player in list(player_order):
            log(trace, "")
            if player == NPC_ID:
                if npc_active:
                    log(trace, "--- NPC行动 ---")
                    log_timing(trace, "NPC行动轮到时", "从当前位置按反方向移动1~6步")
                    npc_progress = move_npc(
                        grid=grid,
                        progress=progress,
                        config=config,
                        npc_progress=npc_progress,
                        rng=rng,
                        skill_state=skill_state,
                        trace=trace,
                    )
                    npc_rank_active = True
                    log_grid(trace, grid, title="NPC行动后位置分布：")
                continue

            if progress[player] >= track_length:
                continue

            current_pos = display_position(progress[player], track_length)
            current_cell = grid[current_pos]
            if player not in current_cell:
                raise RuntimeError(f"runner {player} is missing from position {current_pos}")
            idx_in_cell = current_cell.index(player)

            log(trace, f"--- {format_runner(player)}行动 ---")
            log_block(
                trace,
                "行动开始：",
                f"角色：{format_runner(player)}",
                f"位置：{format_position(current_pos)}",
                f"格内顺序：{format_cell(current_cell)}",
            )

            dice = roll_dice(player, rng)
            extra_steps = 0
            skip_carried_runners = False
            cantarella_move = False

            if player == DENIA_ID:
                extra_steps += check_denia_skill(skill_state, dice, trace)

            if player == 3:
                log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为最后一名")
                rank_for_decision = current_rank(rank_scope(runners, progress, npc_rank_active), progress, grid)
                log_rank_decision(trace, rank_for_decision, npc_rank_active)
                if rank_for_decision[-1] == player:
                    extra_steps = 3
                    log_block(trace, f"{format_runner(player)}技能触发：", "原因：当前最后一名", "效果：额外+3步")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：当前不是最后一名")
            elif player == 5:
                log_timing(trace, "行动开始", f"{format_runner(player)}进行50%独自行动判定")
                if rng.random() <= 0.5:
                    extra_steps = len(current_cell) - 1
                    skip_carried_runners = True
                    log_block(trace, f"{format_runner(player)}技能触发：", "效果：独自行动", f"额外步数：+{extra_steps}")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：50%判定失败")
            elif player == 7:
                log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为本轮最后行动者")
                if player_order[-1] == player:
                    extra_steps = 2
                    log_block(trace, f"{format_runner(player)}技能触发：", "原因：本轮最后行动", "效果：额外+2步")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：不是本轮最后行动者")
            elif player == 8:
                log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为本轮最先行动者")
                if player_order[0] == player:
                    extra_steps = 2
                    log_block(trace, f"{format_runner(player)}技能触发：", "原因：本轮最先行动", "效果：额外+2步")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：不是本轮最先行动者")
            elif player == 9:
                log_timing(trace, "行动开始", f"{format_runner(player)}检查是否处于逐格移动状态")
                cantarella_move = cantarella_state == 1
                if cantarella_move:
                    log_block(trace, f"{format_runner(player)}技能生效：", "效果：本次逐格移动")
                else:
                    log_block(trace, f"{format_runner(player)}技能未生效：", "原因：不处于逐格移动状态")
            elif player == 10:
                log_timing(trace, "行动开始", f"{format_runner(player)}先结算上次保留的额外步数，再检查同格触发")
                extra_steps = zani_extra_steps
                if len(current_cell) > 1 and rng.random() <= 0.4:
                    zani_extra_steps = 2
                    log_block(trace, f"{format_runner(player)}技能触发：", "效果：下一次行动额外+2步")
                else:
                    zani_extra_steps = 0
                    log_block(trace, f"{format_runner(player)}技能未触发：", "效果：下一次行动无额外步数")
            elif player == 11:
                log_timing(trace, "行动开始", f"{format_runner(player)}若已进入强化状态，则检查60%额外+2步")
                if cartethyia_extra_steps and rng.random() <= 0.6:
                    extra_steps = 2
                    log_block(trace, f"{format_runner(player)}技能触发：", "效果：额外+2步")
                elif cartethyia_extra_steps:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：本次60%判定失败")
                else:
                    log_block(trace, f"{format_runner(player)}技能未判定：", "原因：尚未进入强化状态")
            elif player == 12:
                log_timing(trace, "行动开始", f"{format_runner(player)}进行50%额外+1步判定")
                if rng.random() <= 0.5:
                    extra_steps = 1
                    log_block(trace, f"{format_runner(player)}技能触发：", "效果：额外+1步")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：50%判定失败")
            elif player == HIYUKI_ID:
                extra_steps += check_hiyuki_bonus(skill_state, trace)

            total_steps = dice + extra_steps
            if player == 6:
                log_timing(trace, "骰子后", f"{format_runner(player)}进行重复本次骰子的判定")
                if rng.random() <= 0.28:
                    total_steps += dice
                    log_block(trace, f"{format_runner(player)}技能触发：", "效果：重复本次骰子", f"总步数：{total_steps}")
                else:
                    log_block(trace, f"{format_runner(player)}技能未触发：", "原因：本次不重复骰子")

            total_steps = apply_sigrika_debuff(
                player=player,
                total_steps=total_steps,
                debuffed=sigrika_debuffed,
                trace=trace,
            )

            log_block(
                trace,
                f"{format_runner(player)}掷骰结果：",
                f"骰子：{dice}",
                f"额外步数：{extra_steps}",
                f"总步数：{total_steps}",
            )

            if cantarella_move:
                new_progress, cantarella_state, cantarella_group = move_cantarella(
                    grid=grid,
                    progress=progress,
                    config=config,
                    player=player,
                    total_steps=total_steps,
                    rng=rng,
                    cantarella_state=cantarella_state,
                    cantarella_group=cantarella_group,
                    skill_state=skill_state,
                    trace=trace,
                )
            elif skip_carried_runners:
                new_progress = move_single_runner(
                    grid=grid,
                    progress=progress,
                    config=config,
                    player=player,
                    total_steps=total_steps,
                    rng=rng,
                    skill_state=skill_state,
                    trace=trace,
                )
            else:
                new_progress = move_runner_with_left_side(
                    grid=grid,
                    progress=progress,
                    config=config,
                    player=player,
                    idx_in_cell=idx_in_cell,
                    total_steps=total_steps,
                    rng=rng,
                    skill_state=skill_state,
                    trace=trace,
                )

            maybe_trigger_player1_skill_after_action(
                grid=grid,
                progress=progress,
                actor=player,
                track_length=track_length,
                rng=rng,
                trace=trace,
            )

            if player == 11 and cartethyia_available:
                log_timing(trace, "行动结束", f"{format_runner(player)}检查是否处于最后一名，以决定本场后续强化")
                rank_for_decision = current_rank(rank_scope(runners, progress, npc_rank_active), progress, grid)
                log_rank_decision(trace, rank_for_decision, npc_rank_active)
                if rank_for_decision[-1] == player:
                    cartethyia_extra_steps = True
                    cartethyia_available = False
                    log_block(trace, f"{format_runner(player)}技能进入强化状态：", "效果：本场剩余回合可判定额外+2步")
                else:
                    log_block(trace, f"{format_runner(player)}技能未进入强化状态：", "原因：行动结束后不是最后一名")

            log_grid(trace, grid, title="行动后位置分布：")

            if new_progress >= track_length:
                log_timing(trace, "移动结算后", "到达或经过终点，立即进行冠军判定")
                finished = True
                break

        ranking = current_rank(runners, progress, grid)
        if finished:
            second_position = progress[ranking[1]] if len(ranking) > 1 else track_length
            result = RaceResult(
                winner=grid[0][0],
                ranking=tuple(ranking),
                second_position=second_position,
                winner_margin=max(0, track_length - second_position),
            )
            log(
                trace,
                "比赛结束："
            )
            log_block(
                trace,
                "结果：",
                f"冠军：{format_runner(result.winner)}",
                f"排名：{format_runner_list(result.ranking)}",
                f"领先距离：{result.winner_margin}",
            )
            return result

        if npc_active:
            log(trace, "")
            log_timing(trace, "回合结束", "NPC检查是否与最后一名同格，不同格则回到第0格")
            npc_progress = settle_npc_end_of_round(
                grid=grid,
                progress=progress,
                runners=runners,
                npc_progress=npc_progress,
                track_length=track_length,
                trace=trace,
            )

        if 2 in runners:
            log(trace, "")
            log_timing(trace, "回合结束", f"{format_runner(2)}检查是否在同格最右侧之外，以决定下一轮是否最后行动")
            next_turn_last = check_player2_skill(grid, rng, trace)
        else:
            next_turn_last = False
        player_order = next_round_action_order(
            runners=runners,
            rng=rng,
            include_npc=config.npc_enabled and round_number + 1 >= config.npc_start_round,
            player2_last=next_turn_last and 2 in runners,
        )

        if cantarella_state == 2:
            cantarella_state = 0

        round_number += 1


def validate_positions(runners: Sequence[int], progress: dict[int, int]) -> None:
    missing = set(runners) - set(progress)
    if missing:
        raise ValueError(f"missing start positions for: {format_runner_list(sorted(missing))}")


def initial_player_order(config: RaceConfig, grid: dict[int, Sequence[int]], rng: random.Random) -> list[int]:
    if config.initial_order_mode == "random":
        order = list(config.runners)
        rng.shuffle(order)
        return order
    if config.initial_order_mode == "start":
        order = [runner for _, cell in sorted(grid.items()) for runner in cell]
        validate_same_runners(config.runners, order, "initial start order")
        return order
    if config.initial_order_mode == "fixed":
        return list(config.fixed_initial_order)
    raise ValueError(f"unknown initial_order_mode: {config.initial_order_mode}")


def rank_scope(runners: Sequence[int], progress: dict[int, int], include_npc: bool) -> tuple[int, ...]:
    if include_npc and NPC_ID in progress:
        return tuple(runners) + (NPC_ID,)
    return tuple(runners)


def mark_sigrika_debuffs(
    *,
    runners: Sequence[int],
    progress: dict[int, int],
    grid: dict[int, Sequence[int]],
    round_number: int = 2,
    trace: bool | TraceLogger = False,
) -> set[int]:
    if SIGRIKA_ID not in runners:
        return set()
    if round_number == 1:
        log_timing(trace, "回合开始", f"{format_runner(SIGRIKA_ID)}第一轮不发动技能")
        log_block(trace, f"{format_runner(SIGRIKA_ID)}技能不发动：", "原因：第一轮不发动")
        return set()
    ranking = current_rank(runners, progress, grid)
    sigrika_index = ranking.index(SIGRIKA_ID)
    targets = tuple(ranking[max(0, sigrika_index - 2) : sigrika_index])
    log_timing(trace, "回合开始", f"{format_runner(SIGRIKA_ID)}标记排名紧邻且高于自己的至多两名角色")
    log_block(
        trace,
        f"{format_runner(SIGRIKA_ID)}技能判定：",
        "NPC参与排名：否",
        f"名次（前→后）：{format_runner_arrow_list(ranking)}",
        f"标记目标：{format_cell(targets) if targets else '无'}",
        "效果：被标记角色本轮移动总步数-1，最低为1步",
    )
    return set(targets)


def apply_sigrika_debuff(
    *,
    player: int,
    total_steps: int,
    debuffed: set[int],
    trace: bool | TraceLogger = False,
) -> int:
    if player not in debuffed:
        return total_steps
    adjusted_steps = max(1, total_steps - 1)
    log_timing(trace, "移动结算前", f"{format_runner(SIGRIKA_ID)}的减速标记对{format_runner(player)}生效")
    log_block(
        trace,
        f"{format_runner(SIGRIKA_ID)}减速生效：",
        f"原总步数：{total_steps}",
        f"减速后总步数：{adjusted_steps}",
    )
    return adjusted_steps


def check_denia_skill(
    skill_state: RaceSkillState,
    dice: int,
    trace: bool | TraceLogger = False,
) -> int:
    log_timing(trace, "骰子后", f"{format_runner(DENIA_ID)}检查本轮骰点是否与上一轮相同")
    previous = skill_state.denia_last_dice
    skill_state.denia_last_dice = dice
    if previous is None:
        log_block(trace, f"{format_runner(DENIA_ID)}技能不判定：", "原因：没有上一轮骰点记录")
        return 0
    if previous == dice:
        log_block(
            trace,
            f"{format_runner(DENIA_ID)}技能触发：",
            f"上一轮骰点：{previous}",
            f"本轮骰点：{dice}",
            "效果：额外+2步",
        )
        return 2
    log_block(
        trace,
        f"{format_runner(DENIA_ID)}技能未触发：",
        f"上一轮骰点：{previous}",
        f"本轮骰点：{dice}",
    )
    return 0


def check_hiyuki_bonus(skill_state: RaceSkillState, trace: bool | TraceLogger = False) -> int:
    log_timing(trace, "行动开始", f"{format_runner(HIYUKI_ID)}检查与NPC相遇后获得的额外步数")
    if skill_state.hiyuki_bonus_steps <= 0:
        log_block(trace, f"{format_runner(HIYUKI_ID)}技能未生效：", "原因：尚未与NPC相遇")
        return 0
    log_block(
        trace,
        f"{format_runner(HIYUKI_ID)}技能生效：",
        f"当前层数：{skill_state.hiyuki_bonus_steps}",
        f"效果：额外+{skill_state.hiyuki_bonus_steps}步",
    )
    return skill_state.hiyuki_bonus_steps


def next_round_action_order(
    *,
    runners: Sequence[int],
    rng: random.Random,
    include_npc: bool,
    player2_last: bool,
) -> list[int]:
    order = list(runners)
    if include_npc:
        order.append(NPC_ID)
    rng.shuffle(order)
    if player2_last and 2 in order:
        order = [runner for runner in order if runner != 2] + [2]
    return order


def add_npc_to_start(grid: dict[int, list[int]]) -> None:
    remove_runner_from_grid(grid, NPC_ID)
    if grid.get(0):
        grid[0] = list(grid[0]) + [NPC_ID]
    else:
        grid[0] = [NPC_ID]
    keep_npc_rightmost(grid[0])


def roll_dice(player: int, rng: random.Random) -> int:
    if player == 4:
        return rng.randint(2, 3)
    if player == 10:
        return 1 if rng.random() < 0.5 else 3
    return rng.randint(1, 3)


def move_single_runner(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    player: int,
    total_steps: int,
    rng: random.Random,
    skill_state: RaceSkillState | None = None,
    trace: bool | TraceLogger = False,
) -> int:
    track_length = config.track_length
    current_progress = progress[player]
    current_pos = display_position(current_progress, track_length)
    grid[current_pos] = [runner for runner in grid[current_pos] if runner != player]
    new_progress = move_progress(current_progress, total_steps, track_length)
    record_hiyuki_npc_path_contact(
        movers=[player],
        progress=progress,
        track_length=track_length,
        path=forward_path_positions(current_progress, total_steps, track_length),
        skill_state=skill_state,
        trace=trace,
    )
    add_group_to_position(grid, progress, [player], new_progress, rng, config, skill_state, trace)
    return progress[player]


def move_runner_with_left_side(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    player: int,
    idx_in_cell: int,
    total_steps: int,
    rng: random.Random,
    skill_state: RaceSkillState | None = None,
    trace: bool | TraceLogger = False,
) -> int:
    track_length = config.track_length
    current_progress = progress[player]
    current_pos = display_position(current_progress, track_length)
    old_cell = list(grid[current_pos])
    left_runners = old_cell[:idx_in_cell]
    movers = left_runners + [player]
    grid[current_pos] = [runner for runner in old_cell if runner not in movers]
    new_progress = move_progress(current_progress, total_steps, track_length)
    record_hiyuki_npc_path_contact(
        movers=movers,
        progress=progress,
        track_length=track_length,
        path=forward_path_positions(current_progress, total_steps, track_length),
        skill_state=skill_state,
        trace=trace,
    )
    add_group_to_position(grid, progress, movers, new_progress, rng, config, skill_state, trace)
    return progress[player]


def move_cantarella(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    player: int,
    total_steps: int,
    rng: random.Random,
    cantarella_state: int,
    cantarella_group: list[int],
    trace: bool | TraceLogger,
    skill_state: RaceSkillState | None = None,
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
        record_hiyuki_npc_path_contact(
            movers=movers,
            progress=progress,
            track_length=track_length,
            path=forward_path_positions(current_progress, 1, track_length),
            skill_state=skill_state,
            trace=trace,
        )
        add_group_to_position(grid, progress, movers, new_progress, rng, config, skill_state, trace)
        new_progress = progress[player]
        new_pos = display_position(new_progress, track_length)
        log_grid(trace, grid)

        if not group_mode:
            old_set = set(old_cell)
            if any(runner not in old_set for runner in grid[new_pos]):
                group_mode = True
                group = list(grid[new_pos])
                cantarella_state = 2
                log_block(trace, f"{format_runner(player)}技能触发：", "效果：与终点格角色合流")

        if new_progress >= track_length:
            break

    return new_progress, cantarella_state, group


def add_group_to_position(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    new_progress: int,
    rng: random.Random,
    config: RaceConfig,
    skill_state: RaceSkillState | None = None,
    trace: bool | TraceLogger = False,
) -> None:
    track_length = config.track_length
    new_pos = display_position(new_progress, track_length)
    for runner in movers:
        progress[runner] = new_progress
    if grid.get(new_pos):
        grid[new_pos] = list(movers) + grid[new_pos]
    else:
        grid[new_pos] = list(movers)
    keep_npc_rightmost(grid[new_pos])
    log_block(
        trace,
        "落点结算：",
        f"移动队列：{format_cell(movers)}",
        f"到达位置：{format_position(new_pos)}",
        f"格内顺序：{format_cell(grid[new_pos])}",
    )
    apply_cell_effects(grid, progress, movers, new_pos, rng, config, skill_state, trace)


def apply_cell_effects(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    pos: int,
    rng: random.Random,
    config: RaceConfig,
    skill_state: RaceSkillState | None = None,
    trace: bool | TraceLogger = False,
) -> None:
    if pos in config.shuffle_cells or pos in config.forward_cells or pos in config.backward_cells:
        log_timing(trace, "落点结算后", f"检查{format_position(pos)}的赛道特殊格效果")
    if pos in config.shuffle_cells:
        before = list(grid[pos])
        shuffled = shuffle_without_npc(grid[pos], rng)
        grid[pos] = shuffled
        log_block(
            trace,
            f"特殊格 {format_position(pos)}：",
            "效果：随机打乱格内顺序",
            f"打乱对象：{format_cell([runner for runner in before if runner != NPC_ID])}",
            "NPC处理：不参与打乱，结算后固定最右",
            f"打乱前：{format_cell(before)}",
            f"打乱后：{format_cell(grid[pos])}",
        )
    if pos in config.forward_cells:
        move_group_due_to_cell_effect(grid, progress, movers, pos, 1, rng, config, skill_state, trace)
    elif pos in config.backward_cells:
        move_group_due_to_cell_effect(grid, progress, movers, pos, -1, rng, config, skill_state, trace)


def move_group_due_to_cell_effect(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    current_pos: int,
    delta: int,
    rng: random.Random,
    config: RaceConfig,
    skill_state: RaceSkillState | None = None,
    trace: bool | TraceLogger = False,
) -> None:
    active_movers = [runner for runner in movers if runner in grid.get(current_pos, [])]
    if not active_movers:
        return
    delta = adjust_cell_effect_delta(active_movers, delta, trace)
    grid[current_pos] = [runner for runner in grid[current_pos] if runner not in active_movers]
    if not grid[current_pos]:
        grid.pop(current_pos, None)

    base_progress = progress[active_movers[-1]]
    if active_movers == [NPC_ID]:
        new_progress = (base_progress + delta) % config.track_length
    elif delta > 0:
        new_progress = move_progress(base_progress, delta, config.track_length)
    else:
        new_progress = max(MIN_START_POSITION, base_progress + delta)
    new_pos = display_position(new_progress, config.track_length)
    record_hiyuki_npc_path_contact(
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
        progress[runner] = new_progress
    if grid.get(new_pos):
        grid[new_pos] = active_movers + grid[new_pos]
    else:
        grid[new_pos] = active_movers
    keep_npc_rightmost(grid[new_pos])
    direction_text = f"前进{delta}格" if delta > 0 else f"后退{-delta}格"
    log_block(
        trace,
        f"特殊格 {format_position(current_pos)}：",
        f"效果：{direction_text}",
        f"移动队列：{format_cell(active_movers)}",
        f"到达位置：{format_position(new_pos)}",
        f"格内顺序：{format_cell(grid[new_pos])}",
    )


def move_progress(current_progress: int, steps: int, track_length: int) -> int:
    target = current_progress + steps
    return track_length if target >= track_length else target


def move_npc(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    npc_progress: int,
    rng: random.Random,
    trace: bool | TraceLogger,
    skill_state: RaceSkillState | None = None,
) -> int:
    track_length = config.track_length
    remove_runner_from_grid(grid, NPC_ID)
    steps = rng.randint(1, 6)
    new_progress = (npc_progress - steps) % track_length
    new_pos = new_progress
    destination_before = list(grid.get(new_pos, []))
    record_hiyuki_npc_path_contact(
        movers=[NPC_ID],
        progress=progress,
        track_length=track_length,
        path=npc_reverse_path_positions(npc_progress, steps, track_length),
        skill_state=skill_state,
        trace=trace,
    )
    contact_cell = [runner for runner in destination_before if runner != NPC_ID]
    if grid.get(new_pos):
        grid[new_pos] = grid[new_pos] + [NPC_ID]
    else:
        grid[new_pos] = [NPC_ID]
    progress[NPC_ID] = new_progress
    keep_npc_rightmost(grid[new_pos])
    log_block(
        trace,
        "NPC行动：",
        f"后退步数：{steps}",
        f"路径：{format_position(npc_progress % track_length)} -> {format_position(new_pos)}",
        f"接触角色：{format_cell(contact_cell)}",
        f"格内顺序：{format_cell(grid[new_pos])}",
    )
    apply_cell_effects(grid, progress, [NPC_ID], new_pos, rng, config, skill_state, trace)
    return progress[NPC_ID]


def settle_npc_end_of_round(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    runners: Sequence[int],
    npc_progress: int,
    track_length: int,
    trace: bool | TraceLogger,
) -> int:
    npc_pos = npc_progress % track_length
    last_runner = current_rank(runners, progress, grid)[-1]
    last_pos = display_position(progress[last_runner], track_length)
    if npc_pos == last_pos:
        progress[NPC_ID] = npc_progress
        log_block(
            trace,
            "NPC停留：",
            f"原因：与最后一名{format_runner(last_runner)}同格",
            f"位置：{format_position(npc_pos)}",
        )
        return npc_progress
    remove_runner_from_grid(grid, NPC_ID)
    if grid.get(0):
        grid[0] = grid[0] + [NPC_ID]
    else:
        grid[0] = [NPC_ID]
    keep_npc_rightmost(grid[0])
    progress[NPC_ID] = 0
    log_block(
        trace,
        "NPC回到起始格：",
        f"NPC位置：{format_position(npc_pos)}",
        f"最后一名：{format_runner(last_runner)}",
        f"最后一名位置：{format_position(last_pos)}",
    )
    return 0


def remove_runner_from_grid(grid: dict[int, list[int]], runner: int) -> None:
    empty_positions: list[int] = []
    for pos, cell in grid.items():
        if runner in cell:
            grid[pos] = [item for item in cell if item != runner]
            if not grid[pos]:
                empty_positions.append(pos)
    for pos in empty_positions:
        grid.pop(pos, None)


def keep_npc_rightmost(cell: list[int]) -> None:
    if NPC_ID not in cell:
        return
    npc_count = cell.count(NPC_ID)
    cell[:] = [runner for runner in cell if runner != NPC_ID] + [NPC_ID] * npc_count


def shuffle_without_npc(cell: Sequence[int], rng: random.Random) -> list[int]:
    runners = [runner for runner in cell if runner != NPC_ID]
    npc_count = sum(1 for runner in cell if runner == NPC_ID)
    rng.shuffle(runners)
    return runners + [NPC_ID] * npc_count


def adjust_cell_effect_delta(
    movers: Sequence[int],
    delta: int,
    trace: bool | TraceLogger = False,
) -> int:
    if LUUK_HERSSEN_ID not in movers:
        return delta
    adjusted = 4 if delta > 0 else -2
    log_block(
        trace,
        f"{format_runner(LUUK_HERSSEN_ID)}技能触发：",
        f"特殊格原效果：{'前进1格' if delta > 0 else '后退1格'}",
        f"修正后效果：{'前进4格' if adjusted > 0 else '后退2格'}",
    )
    return adjusted


def forward_path_positions(current_progress: int, steps: int, track_length: int) -> list[int]:
    if steps <= 0:
        return []
    final_progress = min(current_progress + steps, track_length)
    return [display_position(progress, track_length) for progress in range(current_progress + 1, final_progress + 1)]


def cell_effect_path_positions(
    *,
    start_progress: int,
    delta: int,
    track_length: int,
    wrap: bool,
) -> list[int]:
    if delta == 0:
        return []
    if wrap:
        direction = 1 if delta > 0 else -1
        return [(start_progress + direction * offset) % track_length for offset in range(1, abs(delta) + 1)]
    if delta > 0:
        return forward_path_positions(start_progress, delta, track_length)
    final_progress = max(MIN_START_POSITION, start_progress + delta)
    return [display_position(progress, track_length) for progress in range(start_progress - 1, final_progress - 1, -1)]


def npc_reverse_path_positions(npc_progress: int, steps: int, track_length: int) -> list[int]:
    return [(npc_progress - offset) % track_length for offset in range(1, steps + 1)]


def record_hiyuki_npc_path_contact(
    *,
    movers: Sequence[int],
    progress: dict[int, int],
    track_length: int,
    path: Sequence[int],
    skill_state: RaceSkillState | None,
    trace: bool | TraceLogger = False,
) -> None:
    if skill_state is None or not path:
        return
    movers_set = set(movers)
    path_positions = set(path)
    reason: str | None = None
    if HIYUKI_ID in movers_set and NPC_ID in progress:
        npc_pos = display_position(progress[NPC_ID], track_length)
        if npc_pos in path_positions:
            reason = f"{format_runner(HIYUKI_ID)}移动路径经过NPC所在{format_position(npc_pos)}"
    elif NPC_ID in movers_set and HIYUKI_ID in progress:
        hiyuki_pos = display_position(progress[HIYUKI_ID], track_length)
        if hiyuki_pos in path_positions:
            reason = f"NPC移动路径经过{format_runner(HIYUKI_ID)}所在{format_position(hiyuki_pos)}"
    if reason is None:
        return
    skill_state.hiyuki_bonus_steps += 1
    log_block(
        trace,
        f"{format_runner(HIYUKI_ID)}技能叠加：",
        f"原因：{reason}",
        f"当前额外步数：+{skill_state.hiyuki_bonus_steps}",
    )


def record_hiyuki_npc_destination_contact_legacy(
    arrivals: Sequence[int],
    destination_before: Sequence[int],
    skill_state: RaceSkillState | None,
    trace: bool | TraceLogger = False,
) -> None:
    """旧版绯雪规则：仅在终点格重合时叠加。保留以便需要时快速回滚。"""
    if skill_state is None:
        return
    arrivals_set = set(arrivals)
    if HIYUKI_ID in arrivals_set and NPC_ID in destination_before:
        reason = f"{format_runner(HIYUKI_ID)}落到NPC所在格"
    elif NPC_ID in arrivals_set and HIYUKI_ID in destination_before:
        reason = f"NPC落到{format_runner(HIYUKI_ID)}所在格"
    else:
        return
    skill_state.hiyuki_bonus_steps += 1
    log_block(
        trace,
        f"{format_runner(HIYUKI_ID)}技能叠加：",
        f"原因：{reason}",
        f"当前额外步数：+{skill_state.hiyuki_bonus_steps}",
    )


def maybe_trigger_player1_skill_after_action(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    actor: int,
    track_length: int,
    rng: random.Random,
    trace: bool | TraceLogger = False,
) -> None:
    if actor in (1, NPC_ID) or 1 not in progress:
        return

    log_timing(trace, "行动结束", f"{format_runner(1)}检查自己所在格左侧是否存在角色")
    pos = display_position(progress[1], track_length)
    cell = grid.get(pos)
    if not cell or 1 not in cell:
        log_block(
            trace,
            f"{format_runner(1)}技能不判定：",
            f"位置：{format_position(pos)}",
            f"原因：{format_runner(1)}不在该格",
        )
        return

    keep_npc_rightmost(cell)
    one_idx = cell.index(1)
    left_runners = [runner for runner in cell[:one_idx] if runner != NPC_ID]
    if not left_runners:
        log_block(
            trace,
            f"{format_runner(1)}技能不判定：",
            f"位置：{format_position(pos)}",
            f"原因：左侧没有角色",
            f"格内顺序：{format_cell(cell)}",
        )
        return

    log_block(
        trace,
        f"{format_runner(1)}技能进入概率判定：",
        f"左侧角色：{format_cell(left_runners)}",
        f"格内顺序：{format_cell(cell)}",
    )
    if rng.random() <= 0.4:
        cell[:] = [1] + [runner for runner in cell if runner != 1]
        keep_npc_rightmost(cell)
        log_block(
            trace,
            f"{format_runner(1)}技能触发：",
            f"原左侧角色：{format_cell(left_runners)}",
            f"格内顺序：{format_cell(cell)}",
        )
    else:
        log_block(
            trace,
            f"{format_runner(1)}技能未触发：",
            "原因：概率判定失败",
            f"格内顺序：{format_cell(cell)}",
        )


def check_player2_skill(
    grid: dict[int, Sequence[int]],
    rng: random.Random,
    trace: bool | TraceLogger = False,
) -> bool:
    for cell in grid.values():
        if 2 in cell and cell.index(2) < len(cell) - 1:
            log_block(
                trace,
                f"{format_runner(2)}技能进入概率判定：",
                f"格内顺序：{format_cell(cell)}",
            )
            if rng.random() <= 0.65:
                log_block(trace, f"{format_runner(2)}技能触发：", "效果：下一轮固定最后行动")
                return True
            log_block(trace, f"{format_runner(2)}技能未触发：", "原因：概率判定失败")
            return False
    log_block(trace, f"{format_runner(2)}技能不判定：", "原因：当前不在同格最右侧之外")
    return False


def current_rank(runners: Sequence[int], progress: dict[int, int], grid: dict[int, Sequence[int]]) -> list[int]:
    cell_index: dict[int, int] = {}
    for cell in grid.values():
        for idx, runner in enumerate(cell):
            if runner != NPC_ID:
                cell_index[runner] = idx
    return sorted(runners, key=lambda runner: (-progress[runner], cell_index.get(runner, 9999)))


def run_monte_carlo(
    config: RaceConfig,
    iterations: int,
    *,
    seed: int | None = None,
    workers: int = 1,
) -> SimulationSummary:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if workers == 0:
        workers = mp.cpu_count()
    workers = max(1, min(workers, iterations))

    if workers == 1:
        acc = simulate_chunk(config, iterations, seed)
        return acc.to_summary(config)

    master_rng = random.Random(seed)
    chunk_sizes = split_iterations(iterations, workers)
    chunk_args = [
        (config, chunk_size, master_rng.randrange(1, 2**63))
        for chunk_size in chunk_sizes
        if chunk_size > 0
    ]
    with mp.Pool(processes=len(chunk_args)) as pool:
        parts = pool.map(simulate_chunk_from_tuple, chunk_args)
    acc = MonteCarloAccumulator(config.runners)
    for part in parts:
        acc.merge(part)
    return acc.to_summary(config)


def simulate_chunk_from_tuple(args: tuple[RaceConfig, int, int | None]) -> MonteCarloAccumulator:
    config, iterations, seed = args
    return simulate_chunk(config, iterations, seed)


def simulate_chunk(config: RaceConfig, iterations: int, seed: int | None) -> MonteCarloAccumulator:
    rng = random.Random(seed)
    acc = MonteCarloAccumulator(config.runners)
    for _ in range(iterations):
        acc.add(simulate_race(config, rng))
    return acc


def split_iterations(iterations: int, workers: int) -> list[int]:
    base, remainder = divmod(iterations, workers)
    return [base + (1 if i < remainder else 0) for i in range(workers)]


def parse_runner(token: str) -> int:
    value = token.strip()
    if not value:
        raise ValueError("empty runner token")
    if value.isdigit():
        runner = int(value)
    elif value in NAME_TO_RUNNER:
        runner = NAME_TO_RUNNER[value]
    else:
        runner = RUNNER_ALIASES.get(value.lower())
        if runner is None:
            raise ValueError(f"unknown runner: {token}")
    if runner not in RUNNER_NAMES:
        raise ValueError(f"unknown runner id: {runner}")
    return runner


def parse_runner_tokens(tokens: Sequence[str] | None) -> tuple[int, ...] | None:
    if not tokens:
        return None
    runners: list[int] = []
    for token in tokens:
        for part in token.split(","):
            if part.strip():
                runners.append(parse_runner(part))
    if len(set(runners)) != len(runners):
        raise ValueError("selected runners contain duplicates")
    return tuple(runners)


def parse_start_spec(spec: str) -> dict[int, tuple[int, ...]]:
    cells, random_start_position = parse_start_layout(spec)
    if random_start_position is not None:
        raise ValueError("use parse_start_layout for '*' random-stack start specs")
    return cells


def parse_start_layout(spec: str) -> tuple[dict[int, tuple[int, ...]], int | None]:
    cells: dict[int, tuple[int, ...]] = {}
    random_start_position: int | None = None
    if not spec.strip():
        raise ValueError("start spec cannot be empty")
    for group in spec.split(";"):
        if not group.strip():
            continue
        if ":" not in group:
            raise ValueError(f"invalid start group {group!r}; expected 'position:runners'")
        pos_text, runners_text = group.split(":", 1)
        pos = int(pos_text.strip())
        if runners_text.strip() == "*":
            if random_start_position is not None:
                raise ValueError("start spec can only contain one '*' random-stack group")
            random_start_position = pos
            continue
        runners = tuple(parse_runner(part) for part in runners_text.split(",") if part.strip())
        if not runners:
            raise ValueError(f"position {pos} has no runners")
        if pos in cells:
            raise ValueError(f"position {pos} is defined more than once")
        cells[pos] = runners
    if random_start_position is not None and cells:
        raise ValueError("'*' means all selected runners start in that cell, so it cannot be mixed with fixed cells")
    all_runners = [runner for runners in cells.values() for runner in runners]
    if len(set(all_runners)) != len(all_runners):
        raise ValueError("start spec contains duplicate runners")
    return cells, random_start_position


def build_config_from_args(args: argparse.Namespace) -> RaceConfig:
    runners = parse_runner_tokens(args.runners)
    season = args.season
    rules = season_rules(season)
    if args.start:
        track_length = args.track_length or DEFAULT_LAP_LENGTH
        if args.track_length is None:
            track_length = int(rules["track_length"])
        start_cells, random_start_position = parse_start_layout(args.start)
        if random_start_position is not None:
            validate_start_position(random_start_position, track_length)
            if runners is None:
                runners = preset_config(args.preset).runners
            grid = empty_grid(track_length)
        else:
            if runners is None:
                runners = tuple(runner for _, cell in sorted(start_cells.items()) for runner in cell)
            grid = make_start_grid(track_length, start_cells)
            validate_fixed_start(runners, grid)
        initial_order_mode = default_initial_order_mode(grid, random_start_position)
        fixed_order: tuple[int, ...] = ()
        if args.initial_order:
            if args.initial_order == "random":
                initial_order_mode = "random"
            elif args.initial_order == "start":
                initial_order_mode = "start"
            else:
                fixed_order = parse_runner_tokens([args.initial_order]) or ()
                validate_same_runners(runners, fixed_order, "fixed initial order")
                initial_order_mode = "fixed"
        return RaceConfig(
            runners=runners,
            track_length=track_length,
            start_grid=grid,
            season=season,
            forward_cells=rules["forward_cells"],
            backward_cells=rules["backward_cells"],
            shuffle_cells=rules["shuffle_cells"],
            npc_enabled=bool(rules["npc_enabled"]),
            random_start_stack=random_start_position is not None,
            random_start_position=random_start_position or 0,
            initial_order_mode=initial_order_mode,
            fixed_initial_order=fixed_order,
            name="custom",
        )

    config = preset_config(args.preset, runners)
    config = apply_season_rules(config, season, args.track_length)
    return config


def default_initial_order_mode(grid: dict[int, Sequence[int]], random_start_position: int | None) -> str:
    nonempty_positions = [pos for pos, cell in grid.items() if cell]
    if random_start_position == 0:
        return "start"
    if nonempty_positions == [0]:
        return "start"
    return "random"


def summary_to_dict(summary: SimulationSummary) -> dict[str, object]:
    return {
        "iterations": summary.iterations,
        "config": {
            "name": summary.config.name,
            "season": summary.config.season,
            "runners": list(summary.config.runners),
            "lap_length": summary.config.track_length,
            "track_length": summary.config.track_length,
            "forward_cells": sorted(summary.config.forward_cells),
            "backward_cells": sorted(summary.config.backward_cells),
            "shuffle_cells": sorted(summary.config.shuffle_cells),
            "npc_enabled": summary.config.npc_enabled,
            "random_start_stack": summary.config.random_start_stack,
            "random_start_position": summary.config.random_start_position,
        },
        "best": {
            "runner": summary.best.runner,
            "name": summary.best.name,
            "win_rate": summary.best.win_rate,
            "average_rank": summary.best.average_rank,
        },
        "rows": [
            {
                "runner": row.runner,
                "name": row.name,
                "wins": row.wins,
                "win_rate": row.win_rate,
                "average_rank": row.average_rank,
                "rank_variance": row.rank_variance,
                "winner_gap_per_race": row.winner_gap_per_race,
                "average_winning_margin": row.average_winning_margin,
            }
            for row in summary.rows
        ],
    }


def format_summary(summary: SimulationSummary, sort_by_win_rate: bool = True) -> str:
    rows = list(summary.rows)
    if sort_by_win_rate:
        rows.sort(key=lambda row: (row.win_rate, -row.average_rank), reverse=True)

    lines = [
        f"Scenario: {summary.config.name}",
        f"Season: {summary.config.season}",
        f"Iterations: {summary.iterations:,}",
        f"Lap length: {summary.config.track_length}",
        "",
        "runner        wins       win_rate   avg_rank   rank_var   gap/race   gap/when_win",
        "------------  ---------  ---------  ---------  ---------  ---------  ------------",
    ]
    for row in rows:
        label = format_runner(row.runner)
        lines.append(
            f"{label:<12}  {row.wins:>9,}  {row.win_rate:>8.2%}  "
            f"{row.average_rank:>9.3f}  {row.rank_variance:>9.3f}  "
            f"{row.winner_gap_per_race:>9.3f}  {row.average_winning_margin:>12.3f}"
        )
    best = summary.best
    lines.extend(
        [
            "",
            f"Best pick: {format_runner(best.runner)} "
            f"with {best.win_rate:.2%} first-place probability.",
        ]
    )
    return "\n".join(lines)


def format_runner_list(runners: Iterable[int]) -> str:
    return ", ".join(format_runner(runner) for runner in runners)


def format_runner_arrow_list(runners: Iterable[int]) -> str:
    return " -> ".join(format_runner(runner) for runner in runners)


def format_runner(runner: int) -> str:
    if runner == NPC_ID:
        return "NPC"
    return RUNNER_NAMES.get(runner, str(runner))


def format_cell(cell: Iterable[int]) -> str:
    return "[" + ", ".join(format_runner(runner) for runner in cell) + "]"


def format_position(pos: int) -> str:
    if pos < 0:
        return f"起点前{-pos}格({pos})"
    return f"第{pos}格"


def format_position_list(positions: Iterable[int]) -> str:
    items = list(positions)
    if not items:
        return "无"
    return "[" + ", ".join(format_position(pos) for pos in items) + "]"


def log(enabled: bool | TraceLogger, message: str) -> None:
    if isinstance(enabled, TraceLogger):
        enabled.write_line(message)
    elif enabled:
        print(message)


def log_timing(enabled: bool | TraceLogger, timing: str, message: str) -> None:
    if not enabled:
        return
    log(enabled, f"【判定时机：{timing}】")
    log(enabled, f"  {message}")
    log(enabled, "")


def log_rank_decision(enabled: bool | TraceLogger, ranking: Sequence[int], npc_rank_active: bool) -> None:
    log_block(
        enabled,
        "当前名次判断：",
        f"NPC参与排名：{'是' if npc_rank_active else '否'}",
        f"名次（前→后）：{format_runner_arrow_list(ranking)}",
        f"当前最后一名：{format_runner(ranking[-1])}",
    )


def log_block(enabled: bool | TraceLogger, title: str, *lines: str) -> None:
    if not enabled:
        return
    log(enabled, title)
    for line in lines:
        log(enabled, f"  {line}")
    log(enabled, "")


def log_grid(
    enabled: bool | TraceLogger,
    grid: dict[int, Sequence[int]],
    title: str | None = None,
) -> None:
    if not enabled:
        return
    if title:
        log(enabled, title)
    wrote_cell = False
    for pos, cell in sorted(grid.items()):
        if cell:
            wrote_cell = True
            log(enabled, f"{format_position(pos)}（左→右）：{format_cell(cell)}")
    if wrote_cell or title:
        log(enabled, "")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulator for Wuthering Waves Cubie Derby.",
    )
    parser.add_argument("-n", "--iterations", type=int, default=100_000, help="number of races to simulate")
    parser.add_argument("--season", type=int, choices=[1, 2], default=1, help="season ruleset")
    parser.add_argument("--preset", type=int, choices=[1, 2, 3, 4, 5], default=4, help="built-in track preset")
    parser.add_argument("--runners", nargs="+", help="runner ids/names, e.g. --runners 3 4 8 10")
    parser.add_argument("--track-length", "--lap-length", dest="track_length", type=int, help="override lap length")
    parser.add_argument(
        "--start",
        help=(
            "custom start grid, e.g. '-3:10;-2:4,3;0:8'. "
            "Use '0:*' to randomly stack all runners in one cell."
        ),
    )
    parser.add_argument(
        "--initial-order",
        help="custom first-round order: 'random', 'start', or comma-separated runner ids",
    )
    parser.add_argument("--seed", type=int, help="random seed for reproducible output")
    parser.add_argument("--workers", type=int, default=1, help="parallel workers; use 0 for CPU count")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--trace", action="store_true", help="print one traced race and exit")
    parser.add_argument("--trace-log", help="write one traced race to this log file and exit")
    return parser


def normalize_cli_args(argv: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--start" and i + 1 < len(argv):
            normalized.append(f"--start={argv[i + 1]}")
            i += 2
        else:
            normalized.append(arg)
            i += 1
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(normalize_cli_args(list(sys.argv[1:] if argv is None else argv)))
    try:
        config = build_config_from_args(args)
        if args.trace or args.trace_log:
            trace = TraceLogger(echo=args.trace)
            result = simulate_race(config, random.Random(args.seed), trace=trace)
            result_text = json.dumps(trace_result_to_dict(result), ensure_ascii=False, indent=2)
            trace.write_line("")
            trace.write_line("=== 结果 ===")
            trace.write_line(result_text)
            if args.trace_log:
                path = Path(args.trace_log)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(trace.text(), encoding="utf-8")
                print(f"过程日志已写入：{path}")
            return 0
        summary = run_monte_carlo(config, args.iterations, seed=args.seed, workers=args.workers)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    if args.json:
        print(json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2))
    else:
        print(format_summary(summary))
    return 0


def trace_result_to_dict(result: RaceResult) -> dict[str, object]:
    return {
        "winner": format_runner(result.winner),
        "winner_id": result.winner,
        "ranking": [format_runner(runner) for runner in result.ranking],
        "ranking_ids": list(result.ranking),
        "second_position": result.second_position,
        "winner_margin": result.winner_margin,
    }


if __name__ == "__main__":
    raise SystemExit(main())
