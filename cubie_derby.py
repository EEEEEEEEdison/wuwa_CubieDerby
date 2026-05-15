from __future__ import annotations

import argparse
from itertools import combinations
import json
import math
import multiprocessing as mp
import random
import sys
import time
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence, TextIO

from cubie_derby_core.runners import (
    AEMEATH_ID,
    AUGUSTA_ID,
    BRANT_ID,
    CALCHARO_ID,
    CAMELLYA_ID,
    CANTARELLA_ID,
    CARTETHYIA_ID,
    CHANGLI_ID,
    CHISA_ID,
    DENIA_ID,
    HIYUKI_ID,
    JINHSI_ID,
    LUNO_ID,
    LUUK_HERSSEN_ID,
    LYNAE_ID,
    MORNYE_ID,
    NAME_TO_RUNNER,
    NPC_ID,
    PHOEBE_ID,
    PHROLOVA_ID,
    POTATO_ID,
    RANDOM_RUNNER_ALIASES,
    ROCCIA_ID,
    RUNNER_ALIASES,
    RUNNER_NAMES,
    SEASON1_RUNNER_POOL,
    SEASON2_RUNNER_POOL,
    SHOREKEEPER_ID,
    SIGRIKA_ID,
    SKILL_RUNNERS,
    ZANI_ID,
)
from cubie_derby_core.movement import (
    MIN_START_POSITION,
    cell_effect_path_positions,
    display_position,
    forward_path_positions,
    keep_npc_rightmost,
    move_progress,
    move_progress_by_delta,
    npc_reverse_path_positions,
    remove_runner_from_grid,
    shuffle_without_npc,
    validate_start_position,
)
from cubie_derby_core.effects import (
    EffectHooks,
    add_group_to_position as core_add_group_to_position,
    adjust_cell_effect_delta as core_adjust_cell_effect_delta,
    apply_cell_effects as core_apply_cell_effects,
    apply_shuffle_cell_effect as core_apply_shuffle_cell_effect,
    move_group_due_to_cell_effect as core_move_group_due_to_cell_effect,
)
from cubie_derby_core.action_flow import (
    PostActionHelpers,
    resolve_post_action_effects as core_resolve_post_action_effects,
)
from cubie_derby_core.match_types import (
    MatchTypeRule,
    effective_qualify_cutoff,
    get_match_type_rule,
    match_type_choices,
    resolve_match_start_spec,
)
from cubie_derby_core.npc import (
    NPCHelpers,
    move_npc as core_move_npc,
    settle_npc_end_of_round as core_settle_npc_end_of_round,
)
from cubie_derby_core.reporting import (
    format_season_roster_scan_summary as core_format_season_roster_scan_summary,
    format_skill_ablation_summary as core_format_skill_ablation_summary,
    format_summary as core_format_summary,
    season_roster_scan_races_per_second as core_season_roster_scan_races_per_second,
    season_roster_scan_to_dict as core_season_roster_scan_to_dict,
    skill_ablation_races_per_second as core_skill_ablation_races_per_second,
    skill_ablation_to_dict as core_skill_ablation_to_dict,
    summary_to_dict as core_summary_to_dict,
)
from cubie_derby_core.skill_hooks import (
    SkillHookHelpers,
    gather_runners_to_luno_cell as core_gather_runners_to_luno_cell,
    maybe_trigger_aemeath_after_active_move as core_maybe_trigger_aemeath_after_active_move,
    maybe_trigger_luno_after_action as core_maybe_trigger_luno_after_action,
    maybe_trigger_player1_skill_after_action as core_maybe_trigger_player1_skill_after_action,
    nearest_runner_progress_ahead as core_nearest_runner_progress_ahead,
    record_hiyuki_npc_path_contact as core_record_hiyuki_npc_path_contact,
)
from cubie_derby_core.skills import (
    apply_chisa_bonus,
    apply_lynae_skill,
    apply_sigrika_debuff,
    check_chisa_skill,
    check_denia_skill,
    check_hiyuki_bonus,
    chisa_has_lowest_dice,
    log_chisa_round_check,
    mark_sigrika_debuffs,
    record_skill_success,
    roll_dice,
    roll_round_dice,
    skill_enabled,
    skill_enabled_from_set,
)
from cubie_derby_core.stage_config import (
    build_race_config as core_build_race_config,
    default_initial_order_mode as core_default_initial_order_mode,
    resolve_match_type_rule as core_resolve_match_type_rule,
)
from cubie_derby_core.tracing import TraceContext
from cubie_derby_core.tournament import (
    ChampionPredictionAccumulator,
    ChampionPredictionSummary,
    StageResult,
    TournamentResult,
    champion_prediction_races_per_second as core_champion_prediction_races_per_second,
    champion_prediction_to_dict as core_champion_prediction_to_dict,
    format_champion_prediction_summary as core_format_champion_prediction_summary,
    format_tournament_result as core_format_tournament_result,
    simulate_stage as core_simulate_stage,
    simulate_tournament as core_simulate_tournament,
    simulate_tournament_chunk as core_simulate_tournament_chunk,
    stage_result_to_dict as core_stage_result_to_dict,
    tournament_result_to_dict as core_tournament_result_to_dict,
    validate_champion_prediction_season as core_validate_champion_prediction_season,
)


DEFAULT_LAP_LENGTH = 24
SEASON2_LAP_LENGTH = 32
AEMEATH_TRIGGER_CELL = 17
SEASON2_FORWARD_CELLS = frozenset({3, 11, 16, 23})
SEASON2_BACKWARD_CELLS = frozenset({10, 28})
SEASON2_SHUFFLE_CELLS = frozenset({6, 20})
RNG_SEED_MASK = (1 << 64) - 1
CAMELLYA_SOLO_ACTION_CHANCE = 0.5
ZANI_EXTRA_STEPS_CHANCE = 0.4
CARTETHYIA_EXTRA_STEPS_CHANCE = 0.6
PHOEBE_EXTRA_STEP_CHANCE = 0.5
POTATO_REPEAT_DICE_CHANCE = 0.28
JINHSI_REORDER_CHANCE = 0.4
CHANGLI_EXTRA_STEP_CHANCE = 0.65

_EFFECT_HOOKS: EffectHooks | None = None
_NPC_HELPERS: NPCHelpers | None = None
_POST_ACTION_HELPERS: PostActionHelpers | None = None
_SKILL_HOOK_HELPERS: SkillHookHelpers | None = None


@dataclass(frozen=True)
class RaceConfig:
    runners: tuple[int, ...]
    track_length: int
    start_grid: dict[int, tuple[int, ...]]
    qualify_cutoff: int = 4
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
    disabled_skills: frozenset[int] = field(default_factory=frozenset)
    match_type: str | None = None
    show_qualify_stats: bool = True
    name: str = "自定义"


@dataclass(frozen=True)
class RaceResult:
    winner: int
    ranking: tuple[int, ...]
    second_position: int
    winner_margin: int
    winner_carried_steps: int = 0
    winner_total_steps: int = 0
    movement_stats: tuple[tuple[int, int, int], ...] = ()
    skill_success_counts: tuple[tuple[int, int], ...] = ()


@dataclass
class RaceSkillState:
    hiyuki_bonus_steps: int = 0
    denia_last_dice: int | None = None
    mornye_next_dice: int = 3
    aemeath_available: bool = True
    aemeath_ready: bool = False
    augusta_force_last_next_round: bool = False
    luno_available: bool = True
    success_counts: dict[int, int] = field(default_factory=dict)


@dataclass
class RaceMovementState:
    total_steps: dict[int, int] = field(default_factory=dict)
    carried_steps: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSuccessBucket:
    success_count: int
    races: int
    wins: int
    win_rate: float


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


class ProgressBar:
    def __init__(
        self,
        total: int,
        label: str,
        *,
        enabled: bool = True,
        stream: TextIO | None = None,
    ) -> None:
        self.total = max(1, total)
        self.label = label
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self.current = 0
        self.started_at = time.perf_counter()
        self.last_render_at = 0.0
        self.last_message_width = 0
        self.closed = False
        if self.enabled:
            self.render(now=self.started_at)

    def advance(self, amount: int) -> None:
        if not self.enabled or self.closed or amount <= 0:
            return
        self.current = min(self.total, self.current + amount)
        now = time.perf_counter()
        if self.current < self.total and now - self.last_render_at < 0.1:
            return
        self.render(now)

    def render(self, now: float | None = None) -> None:
        if not self.enabled or self.closed:
            return
        now = time.perf_counter() if now is None else now
        ratio = self.current / self.total
        width = 28
        filled = min(width, int(ratio * width))
        bar = "#" * filled + "-" * (width - filled)
        elapsed = max(now - self.started_at, 1e-9)
        speed = self.current / elapsed
        message = (
            f"\r{self.label} [{bar}] {ratio:6.2%} "
            f"({self.current:,}/{self.total:,}) {speed:,.0f} 局/秒"
        )
        padding = " " * max(0, self.last_message_width - len(message))
        self.stream.write(message + padding)
        self.stream.flush()
        self.last_message_width = len(message)
        self.last_render_at = now

    def close(self) -> None:
        if not self.enabled or self.closed:
            return
        self.current = self.total
        self.render()
        self.stream.write("\n")
        self.stream.flush()
        self.closed = True


@dataclass(frozen=True)
class RunnerSummary:
    runner: int
    name: str
    wins: int
    win_rate: float
    qualify_count: int
    qualify_rate: float
    average_rank: float
    rank_variance: float
    winner_gap_per_race: float
    average_winning_margin: float
    lazy_win_rate: float = 0.0
    winner_carried_steps: int = 0
    winner_total_steps: int = 0
    skill_average_success_count: float = 0.0
    skill_marginal_win_rate: float | None = None
    skill_success_distribution: tuple[SkillSuccessBucket, ...] = ()


@dataclass(frozen=True)
class SimulationSummary:
    iterations: int
    config: RaceConfig
    rows: tuple[RunnerSummary, ...]
    elapsed_seconds: float | None = None

    @property
    def best(self) -> RunnerSummary:
        return max(self.rows, key=lambda row: (row.win_rate, -row.average_rank))


@dataclass(frozen=True)
class SkillAblationRow:
    runner: int
    name: str
    enabled_win_rate: float
    disabled_win_rate: float
    net_win_rate: float
    skill_average_success_count: float
    skill_marginal_win_rate: float | None
    success_distribution: tuple[SkillSuccessBucket, ...]


@dataclass(frozen=True)
class SkillAblationSummary:
    iterations: int
    total_simulated_races: int
    base_summary: SimulationSummary
    rows: tuple[SkillAblationRow, ...]
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class SeasonRosterScanRow:
    runner: int
    name: str
    combination_count: int
    race_count: int
    wins: int
    win_rate: float
    qualify_count: int
    qualify_rate: float
    average_rank: float
    rank_variance: float
    winner_gap_per_race: float
    average_winning_margin: float
    lazy_win_rate: float = 0.0
    winner_carried_steps: int = 0
    winner_total_steps: int = 0


@dataclass(frozen=True)
class SeasonRosterScanSummary:
    season: int
    roster: tuple[int, ...]
    field_size: int
    qualify_cutoff: int
    iterations_per_combination: int
    combination_count: int
    total_simulated_races: int
    start_spec: str
    track_length: int
    initial_order_mode: str
    rows: tuple[SeasonRosterScanRow, ...]
    elapsed_seconds: float | None = None

    @property
    def best(self) -> SeasonRosterScanRow:
        return max(self.rows, key=lambda row: (row.win_rate, -row.average_rank))


class MonteCarloAccumulator:
    def __init__(self, runners: Sequence[int], qualify_cutoff: int = 4) -> None:
        self.runners = tuple(runners)
        self.index = {runner: i for i, runner in enumerate(self.runners)}
        size = len(self.runners)
        validate_qualify_cutoff(qualify_cutoff, len(self.runners))
        self.qualify_cutoff = min(qualify_cutoff, len(self.runners))
        self.iterations = 0
        self.wins = [0] * size
        self.qualify = [0] * size
        self.rank_sum = [0.0] * size
        self.rank_square_sum = [0.0] * size
        self.winner_gap_sum = [0.0] * size
        self.winner_carried_step_sum = [0] * size
        self.winner_total_step_sum = [0] * size
        self.skill_success_sum = [0.0] * size
        self.skill_success_square_sum = [0.0] * size
        self.skill_success_win_cross_sum = [0.0] * size
        self.skill_success_distribution: list[dict[int, list[int]]] = [dict() for _ in self.runners]

    def add(self, result: RaceResult) -> None:
        self.iterations += 1
        winner_idx = self.index[result.winner]
        self.wins[winner_idx] += 1
        self.winner_gap_sum[winner_idx] += result.winner_margin
        self.winner_carried_step_sum[winner_idx] += result.winner_carried_steps
        self.winner_total_step_sum[winner_idx] += result.winner_total_steps
        skill_counts = dict(result.skill_success_counts)
        for rank, runner in enumerate(result.ranking, start=1):
            idx = self.index[runner]
            if rank <= self.qualify_cutoff:
                self.qualify[idx] += 1
            self.rank_sum[idx] += rank
            self.rank_square_sum[idx] += rank * rank
            success_count = skill_counts.get(runner, 0)
            won = 1 if result.winner == runner else 0
            self.skill_success_sum[idx] += success_count
            self.skill_success_square_sum[idx] += success_count * success_count
            self.skill_success_win_cross_sum[idx] += success_count * won
            bucket = self.skill_success_distribution[idx].setdefault(success_count, [0, 0])
            bucket[0] += 1
            bucket[1] += won

    def merge(self, other: "MonteCarloAccumulator") -> None:
        if self.runners != other.runners:
            raise ValueError("cannot merge accumulators for different runner sets")
        self.iterations += other.iterations
        for i in range(len(self.runners)):
            self.wins[i] += other.wins[i]
            self.qualify[i] += other.qualify[i]
            self.rank_sum[i] += other.rank_sum[i]
            self.rank_square_sum[i] += other.rank_square_sum[i]
            self.winner_gap_sum[i] += other.winner_gap_sum[i]
            self.winner_carried_step_sum[i] += other.winner_carried_step_sum[i]
            self.winner_total_step_sum[i] += other.winner_total_step_sum[i]
            self.skill_success_sum[i] += other.skill_success_sum[i]
            self.skill_success_square_sum[i] += other.skill_success_square_sum[i]
            self.skill_success_win_cross_sum[i] += other.skill_success_win_cross_sum[i]
            for success_count, bucket in other.skill_success_distribution[i].items():
                merged_bucket = self.skill_success_distribution[i].setdefault(success_count, [0, 0])
                merged_bucket[0] += bucket[0]
                merged_bucket[1] += bucket[1]

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
            skill_average_success_count = self.skill_success_sum[idx] / n if n else 0.0
            winner_total_steps = self.winner_total_step_sum[idx]
            winner_carried_steps = self.winner_carried_step_sum[idx]
            if n:
                success_mean = skill_average_success_count
                win_mean = wins / n
                success_square_mean = self.skill_success_square_sum[idx] / n
                success_win_mean = self.skill_success_win_cross_sum[idx] / n
                success_variance = success_square_mean - success_mean * success_mean
                skill_marginal_win_rate = (
                    (success_win_mean - success_mean * win_mean) / success_variance
                    if success_variance > 1e-12
                    else None
                )
            else:
                skill_marginal_win_rate = None
            distribution = tuple(
                SkillSuccessBucket(
                    success_count=success_count,
                    races=bucket[0],
                    wins=bucket[1],
                    win_rate=bucket[1] / bucket[0] if bucket[0] else 0.0,
                )
                for success_count, bucket in sorted(self.skill_success_distribution[idx].items())
            )
            rows.append(
                RunnerSummary(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    wins=wins,
                    win_rate=wins / n if n else 0.0,
                    qualify_count=self.qualify[idx],
                    qualify_rate=self.qualify[idx] / n if n else 0.0,
                    average_rank=avg_rank,
                    rank_variance=variance,
                    winner_gap_per_race=self.winner_gap_sum[idx] / n if n else 0.0,
                    average_winning_margin=self.winner_gap_sum[idx] / wins if wins else 0.0,
                    lazy_win_rate=winner_carried_steps / winner_total_steps if winner_total_steps else 0.0,
                    winner_carried_steps=winner_carried_steps,
                    winner_total_steps=winner_total_steps,
                    skill_average_success_count=skill_average_success_count,
                    skill_marginal_win_rate=skill_marginal_win_rate,
                    skill_success_distribution=distribution,
                )
            )
        return SimulationSummary(iterations=n, config=config, rows=tuple(rows))


class SeasonRosterScanAccumulator:
    def __init__(self, roster: Sequence[int]) -> None:
        self.roster = tuple(roster)
        self.index = {runner: i for i, runner in enumerate(self.roster)}
        size = len(self.roster)
        self.combination_count = [0] * size
        self.race_count = [0] * size
        self.wins = [0] * size
        self.qualify = [0] * size
        self.rank_sum = [0.0] * size
        self.rank_square_sum = [0.0] * size
        self.winner_gap_sum = [0.0] * size
        self.winner_carried_step_sum = [0] * size
        self.winner_total_step_sum = [0] * size

    def add_summary(self, summary: SimulationSummary) -> None:
        n = summary.iterations
        for row in summary.rows:
            idx = self.index[row.runner]
            self.combination_count[idx] += 1
            self.race_count[idx] += n
            self.wins[idx] += row.wins
            self.qualify[idx] += row.qualify_count
            self.rank_sum[idx] += row.average_rank * n
            if n > 1:
                rank_square_sum = row.rank_variance * (n - 1) + ((row.average_rank * n) ** 2) / n
            else:
                rank_square_sum = row.average_rank * row.average_rank
            self.rank_square_sum[idx] += rank_square_sum
            self.winner_gap_sum[idx] += row.winner_gap_per_race * n
            self.winner_carried_step_sum[idx] += row.winner_carried_steps
            self.winner_total_step_sum[idx] += row.winner_total_steps

    def to_summary(
        self,
        *,
        season: int,
        field_size: int,
        qualify_cutoff: int,
        iterations_per_combination: int,
        combination_count: int,
        start_spec: str,
        track_length: int,
        initial_order_mode: str,
        elapsed_seconds: float | None = None,
    ) -> SeasonRosterScanSummary:
        rows: list[SeasonRosterScanRow] = []
        for runner in self.roster:
            idx = self.index[runner]
            race_count = self.race_count[idx]
            wins = self.wins[idx]
            rank_sum = self.rank_sum[idx]
            if race_count:
                average_rank = rank_sum / race_count
                if race_count > 1:
                    variance = (self.rank_square_sum[idx] - (rank_sum * rank_sum) / race_count) / (race_count - 1)
                    variance = max(0.0, variance)
                else:
                    variance = 0.0
                win_rate = wins / race_count
                qualify_rate = self.qualify[idx] / race_count
                winner_gap_per_race = self.winner_gap_sum[idx] / race_count
            else:
                average_rank = math.nan
                variance = math.nan
                win_rate = 0.0
                qualify_rate = 0.0
                winner_gap_per_race = 0.0
            winner_total_steps = self.winner_total_step_sum[idx]
            winner_carried_steps = self.winner_carried_step_sum[idx]
            rows.append(
                SeasonRosterScanRow(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    combination_count=self.combination_count[idx],
                    race_count=race_count,
                    wins=wins,
                    win_rate=win_rate,
                    qualify_count=self.qualify[idx],
                    qualify_rate=qualify_rate,
                    average_rank=average_rank,
                    rank_variance=variance,
                    winner_gap_per_race=winner_gap_per_race,
                    average_winning_margin=self.winner_gap_sum[idx] / wins if wins else 0.0,
                    lazy_win_rate=winner_carried_steps / winner_total_steps if winner_total_steps else 0.0,
                    winner_carried_steps=winner_carried_steps,
                    winner_total_steps=winner_total_steps,
                )
            )
        return SeasonRosterScanSummary(
            season=season,
            roster=self.roster,
            field_size=field_size,
            qualify_cutoff=qualify_cutoff,
            iterations_per_combination=iterations_per_combination,
            combination_count=combination_count,
            total_simulated_races=combination_count * iterations_per_combination,
            start_spec=start_spec,
            track_length=track_length,
            initial_order_mode=initial_order_mode,
            rows=tuple(rows),
            elapsed_seconds=elapsed_seconds,
        )


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


def season_runner_pool(season: int) -> tuple[int, ...]:
    if season == 1:
        return SEASON1_RUNNER_POOL
    if season == 2:
        return SEASON2_RUNNER_POOL
    raise ValueError(f"unknown season: {season}")


def empty_grid(track_length: int) -> dict[int, tuple[int, ...]]:
    validate_track_length(track_length)
    return {}


def validate_track_length(track_length: int) -> None:
    if track_length <= 0:
        raise ValueError("track_length must be positive")


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


def validate_qualify_cutoff(qualify_cutoff: int, field_size: int) -> None:
    if qualify_cutoff < 1:
        raise ValueError("qualify cutoff must be at least 1")


def resolve_qualify_cutoff(args: argparse.Namespace) -> int:
    return getattr(args, "qualify_cutoff", 4)


def record_movement(
    movement_state: RaceMovementState | None,
    movers: Sequence[int],
    distance: int,
    *,
    active_player: int | None,
) -> None:
    if movement_state is None or distance <= 0:
        return
    for runner in movers:
        if runner <= 0:
            continue
        movement_state.total_steps[runner] = movement_state.total_steps.get(runner, 0) + distance
        if active_player is not None and runner != active_player:
            movement_state.carried_steps[runner] = movement_state.carried_steps.get(runner, 0) + distance


def simulate_race(config: RaceConfig, rng: random.Random, trace: TraceContext = False) -> RaceResult:
    runners = config.runners
    track_length = config.track_length
    grid = {pos: list(cell) for pos, cell in config.start_grid.items() if cell}

    if config.random_start_stack:
        validate_start_position(config.random_start_position, track_length)
        start_stack = list(runners)
        rng.shuffle(start_stack)
        grid = {config.random_start_position: start_stack}
    if config.npc_enabled:
        add_npc_to_start(grid)

    progress: dict[int, int] = {}
    for pos, cell in grid.items():
        for runner in cell:
            if runner == NPC_ID:
                continue
            progress[runner] = pos
    validate_positions(runners, progress)

    player_order = initial_player_order(config, grid, rng)
    cantarella_state = 1
    cantarella_group: list[int] = []
    zani_extra_steps = 0
    cartethyia_available = True
    cartethyia_extra_steps = False
    skill_state = RaceSkillState()
    movement_state = RaceMovementState()
    npc_progress = 0
    npc_active = False
    npc_rank_active = False

    round_number = 1
    if trace:
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
            if trace:
                log_block(trace, "NPC登场：", f"出发位置：{format_position(0)}")

        if trace:
            log(trace, f"\n=== 第{round_number}轮 ===")
            log_grid(trace, grid, title="本轮开始时位置分布：")
        if trace and npc_active:
            log_block(trace, "NPC状态：", f"当前位置：{format_position(display_position(npc_progress, track_length))}")
        sigrika_debuffed = mark_sigrika_debuffs(
            runners=runners,
            progress=progress,
            grid=grid,
            round_number=round_number,
            skip_first_round=config.random_start_stack,
            disabled_skills=config.disabled_skills,
            trace=trace,
        )
        round_dice = roll_round_dice(player_order, rng, config=config, skill_state=skill_state)
        chisa_bonus_active = (
            CHISA_ID in player_order
            and skill_enabled(config, CHISA_ID)
            and chisa_has_lowest_dice(round_dice[CHISA_ID], round_dice)
        )
        if trace:
            log_block(trace, "本轮行动顺序：", format_runner_arrow_list(player_order))
            log_block(trace, "本轮骰点：", format_round_dice(round_dice, player_order))
            if CHISA_ID in player_order and skill_enabled(config, CHISA_ID):
                log_chisa_round_check(round_dice[CHISA_ID], round_dice, chisa_bonus_active, trace)

        finished = False
        for player in list(player_order):
            if trace:
                log(trace, "")
            if player == NPC_ID:
                if npc_active:
                    if trace:
                        log(trace, "--- NPC行动 ---")
                        log_timing(trace, "NPC行动轮到时", "从当前位置按反方向移动1~6步")
                    npc_progress = move_npc(
                        grid=grid,
                        progress=progress,
                        config=config,
                        npc_progress=npc_progress,
                        rng=rng,
                        steps=round_dice[player],
                        skill_state=skill_state,
                        movement_state=movement_state,
                        ignore_waiting_stack=round_number == config.npc_start_round,
                        trace=trace,
                    )
                    npc_rank_active = True
                    if trace:
                        log_grid(trace, grid, title="NPC行动后位置分布：")
                continue

            if progress[player] >= track_length:
                continue

            action_start_progress = progress[player]
            current_pos = display_position(action_start_progress, track_length)
            current_cell = grid[current_pos]
            if player not in current_cell:
                raise RuntimeError(f"runner {player} is missing from position {current_pos}")
            idx_in_cell = current_cell.index(player)

            if trace:
                log(trace, f"--- {format_runner(player)}行动 ---")
                log_block(
                    trace,
                    "行动开始：",
                    f"角色：{format_runner(player)}",
                    f"位置：{format_position(current_pos)}",
                    f"格内顺序：{format_cell(current_cell)}",
                )

            dice = round_dice[player]
            extra_steps = 0
            skip_carried_runners = False
            cantarella_move = False
            augusta_skip_turn = False

            if player == AUGUSTA_ID and skill_enabled(config, AUGUSTA_ID):
                non_npc_cell = [runner for runner in current_cell if runner != NPC_ID]
                if skill_state.augusta_force_last_next_round:
                    skill_state.augusta_force_last_next_round = False
                    if trace:
                        log_block(
                            trace,
                            f"{format_runner(player)}技能本回合不判定：",
                            "原因：上一回合已触发停行动作",
                            "效果：本回合仅保留固定最后行动",
                        )
                elif round_number == 1 and config.random_start_stack:
                    if trace:
                        log_block(
                            trace,
                            f"{format_runner(player)}技能本回合不判定：",
                            "原因：随机同格开局时，第一回合不发动技能",
                        )
                else:
                    if trace:
                        log_timing(trace, "行动开始", f"{format_runner(player)}检查自己是否位于同格最左侧且同格存在其他角色")
                    if len(non_npc_cell) > 1 and non_npc_cell[0] == player:
                        augusta_skip_turn = True
                        skill_state.augusta_force_last_next_round = True
                        record_skill_success(skill_state, player)
                        if trace:
                            log_block(
                                trace,
                                f"{format_runner(player)}技能触发：",
                                "原因：自己位于同格最左侧，且同格存在其他角色",
                                "效果：本回合不行动，下回合固定最后行动且不再判定自身技能",
                            )
                    elif trace:
                        log_block(
                            trace,
                            f"{format_runner(player)}技能未触发：",
                            "原因：当前不满足最左侧且同格有其他角色",
                            f"格内顺序：{format_cell(current_cell)}",
                        )

            if player == DENIA_ID and skill_enabled(config, DENIA_ID):
                extra_steps += check_denia_skill(skill_state, dice, trace)
            if player == CHISA_ID and skill_enabled(config, CHISA_ID):
                extra_steps += apply_chisa_bonus(skill_state, chisa_bonus_active, trace)

            if player == CALCHARO_ID and skill_enabled(config, CALCHARO_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为最后一名")
                rank_for_decision = current_rank(rank_scope(runners, progress, npc_rank_active), progress, grid)
                log_rank_decision(trace, rank_for_decision, npc_rank_active)
                if rank_for_decision[-1] == player:
                    extra_steps = 3
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "原因：当前最后一名", "效果：额外+3步")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：当前不是最后一名")
            elif player == CAMELLYA_ID and skill_enabled(config, CAMELLYA_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}进行50%独自行动判定")
                if rng.random() <= CAMELLYA_SOLO_ACTION_CHANCE:
                    extra_steps = len(current_cell) - 1
                    skip_carried_runners = True
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "效果：独自行动", f"额外步数：+{extra_steps}")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：50%判定失败")
            elif player == ROCCIA_ID and skill_enabled(config, ROCCIA_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为本轮最后行动者")
                if player_order[-1] == player:
                    extra_steps = 2
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "原因：本轮最后行动", "效果：额外+2步")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：不是本轮最后行动者")
            elif player == BRANT_ID and skill_enabled(config, BRANT_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}检查是否为本轮最先行动者")
                if player_order[0] == player:
                    extra_steps = 2
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "原因：本轮最先行动", "效果：额外+2步")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：不是本轮最先行动者")
            elif player == CANTARELLA_ID and skill_enabled(config, CANTARELLA_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}检查是否处于逐格移动状态")
                cantarella_move = cantarella_state == 1
                if cantarella_move:
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能生效：", "效果：本次逐格移动")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未生效：", "原因：不处于逐格移动状态")
            elif player == ZANI_ID and skill_enabled(config, ZANI_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}先结算上次保留的额外步数，再检查同格触发")
                extra_steps = zani_extra_steps
                if len(current_cell) > 1 and rng.random() <= ZANI_EXTRA_STEPS_CHANCE:
                    zani_extra_steps = 2
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "效果：下一次行动额外+2步")
                else:
                    zani_extra_steps = 0
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "效果：下一次行动无额外步数")
            elif player == CARTETHYIA_ID and skill_enabled(config, CARTETHYIA_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}若已进入强化状态，则检查60%额外+2步")
                if cartethyia_extra_steps and rng.random() <= CARTETHYIA_EXTRA_STEPS_CHANCE:
                    extra_steps = 2
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "效果：额外+2步")
                elif cartethyia_extra_steps:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：本次60%判定失败")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未判定：", "原因：尚未进入强化状态")
            elif player == PHOEBE_ID and skill_enabled(config, PHOEBE_ID):
                if trace:
                    log_timing(trace, "行动开始", f"{format_runner(player)}进行50%额外+1步判定")
                if rng.random() <= PHOEBE_EXTRA_STEP_CHANCE:
                    extra_steps = 1
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "效果：额外+1步")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：50%判定失败")
            elif player == HIYUKI_ID and skill_enabled(config, HIYUKI_ID):
                extra_steps += check_hiyuki_bonus(skill_state, trace)

            total_steps = dice + extra_steps
            if player == POTATO_ID and skill_enabled(config, POTATO_ID):
                if trace:
                    log_timing(trace, "骰子后", f"{format_runner(player)}进行重复本次骰子的判定")
                if rng.random() <= POTATO_REPEAT_DICE_CHANCE:
                    total_steps += dice
                    record_skill_success(skill_state, player)
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能触发：", "效果：重复本次骰子", f"总步数：{total_steps}")
                else:
                    if trace:
                        log_block(trace, f"{format_runner(player)}技能未触发：", "原因：本次不重复骰子")

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
                        log_block(
                            trace,
                            f"{format_runner(player)}技能本回合不判定：",
                            "原因：随机同格开局时，第一回合不发动技能",
                        )
                else:
                    if trace:
                        log_timing(trace, "行动开始", f"{format_runner(player)}检查自己是否位于同格最右侧且同格存在其他角色")
                    if len(non_npc_cell) > 1 and non_npc_cell[-1] == player:
                        extra_steps += 3
                        total_steps += 3
                        record_skill_success(skill_state, player)
                        if trace:
                            log_block(
                                trace,
                                f"{format_runner(player)}技能触发：",
                                "原因：自己位于同格最右侧，且同格存在其他角色",
                                "效果：本回合额外前进3格",
                            )
                    elif trace:
                        log_block(
                            trace,
                            f"{format_runner(player)}技能未触发：",
                            "原因：当前不满足最右侧且同格有其他角色",
                            f"格内顺序：{format_cell(current_cell)}",
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

            if trace:
                log_block(
                    trace,
                    f"{format_runner(player)}掷骰结果：",
                    f"骰子：{dice}",
                    f"额外步数：{extra_steps}",
                    f"总步数：{total_steps}",
                )

            if total_steps <= 0:
                new_progress = progress[player]
                current_pos = display_position(new_progress, track_length)
                if trace:
                    log_block(
                        trace,
                        f"{format_runner(player)}本回合无法移动：",
                        "移动结算：视为主动移动0格，原地停留",
                        "后续：若当前停留格是打乱格，则触发打乱效果；随后仍按行动结束后的最终站位结算今汐技能判定",
                    )
                if current_pos in config.shuffle_cells:
                    if trace:
                        log_timing(trace, "行动结束", f"检查{format_position(current_pos)}是否为打乱顺序格")
                    apply_shuffle_cell_effect(grid, current_pos, rng, trace=trace)
                new_progress = progress[player]
            elif cantarella_move:
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
                    movement_state=movement_state,
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
                    movement_state=movement_state,
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
                    movement_state=movement_state,
                    trace=trace,
                )

            if new_progress >= track_length:
                if trace:
                    log_grid(trace, grid, title="行动后位置分布：")
                    log_timing(trace, "移动结算后", "到达或经过终点，立即进行冠军判定")
                finished = True
                break

            post_action_state = core_resolve_post_action_effects(
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
                helpers=_post_action_helpers(),
            )
            new_progress = post_action_state.new_progress
            cartethyia_available = post_action_state.cartethyia_available
            cartethyia_extra_steps = post_action_state.cartethyia_extra_steps

            if trace:
                log_grid(trace, grid, title="行动后位置分布：")

        ranking = current_rank(runners, progress, grid)
        if finished:
            second_position = progress[ranking[1]] if len(ranking) > 1 else track_length
            winner = grid[0][0]
            result = RaceResult(
                winner=winner,
                ranking=tuple(ranking),
                second_position=second_position,
                winner_margin=max(0, track_length - second_position),
                winner_carried_steps=movement_state.carried_steps.get(winner, 0),
                winner_total_steps=movement_state.total_steps.get(winner, 0),
                movement_stats=tuple(
                    (runner, movement_state.total_steps.get(runner, 0), movement_state.carried_steps.get(runner, 0))
                    for runner in runners
                ),
                skill_success_counts=tuple(sorted(skill_state.success_counts.items())),
            )
            if trace:
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
            if trace:
                log(trace, "")
                log_timing(trace, "回合结束", "NPC检查自身位置是否小于最后一名位置，若小于则回到第0格")
            npc_progress = settle_npc_end_of_round(
                grid=grid,
                progress=progress,
                runners=runners,
                npc_progress=npc_progress,
                track_length=track_length,
                trace=trace,
            )

        if CHANGLI_ID in runners:
            if trace:
                log(trace, "")
                log_timing(trace, "回合结束", f"{format_runner(CHANGLI_ID)}检查是否在同格最右侧之外，以决定下一轮是否最后行动")
            next_turn_last = check_player2_skill(
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

        player_order = next_round_action_order(
            runners=runners,
            rng=rng,
            include_npc=config.npc_enabled and round_number + 1 >= config.npc_start_round,
            forced_last_runners=tuple(forced_last_runners),
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
        order = [runner for _, cell in sorted(grid.items()) for runner in cell if runner != NPC_ID]
        validate_same_runners(config.runners, order, "initial start order")
        return order
    if config.initial_order_mode == "fixed":
        return list(config.fixed_initial_order)
    raise ValueError(f"unknown initial_order_mode: {config.initial_order_mode}")
def rank_scope(runners: Sequence[int], progress: dict[int, int], include_npc: bool) -> tuple[int, ...]:
    if include_npc and NPC_ID in progress:
        return tuple(runners) + (NPC_ID,)
    return tuple(runners)


def next_round_action_order(
    *,
    runners: Sequence[int],
    rng: random.Random,
    include_npc: bool,
    forced_last_runners: Sequence[int] = (),
) -> list[int]:
    order = list(runners)
    if include_npc:
        order.append(NPC_ID)
    rng.shuffle(order)
    trailing: list[int] = []
    trailing_set: set[int] = set()
    for runner in forced_last_runners:
        if runner in order and runner not in trailing_set:
            trailing.append(runner)
            trailing_set.add(runner)
    if trailing:
        order = [runner for runner in order if runner not in trailing_set] + trailing
    return order


def add_npc_to_start(grid: dict[int, list[int]]) -> None:
    remove_runner_from_grid(grid, NPC_ID)
    if grid.get(0):
        grid[0] = list(grid[0]) + [NPC_ID]
    else:
        grid[0] = [NPC_ID]
    keep_npc_rightmost(grid[0])


def format_round_dice(round_dice: dict[int, int], player_order: Sequence[int]) -> str:
    return "；".join(f"{format_runner(player)}={round_dice[player]}" for player in player_order if player in round_dice)


def move_single_runner(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    player: int,
    total_steps: int,
    rng: random.Random,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
) -> int:
    track_length = config.track_length
    current_progress = progress[player]
    current_pos = display_position(current_progress, track_length)
    grid[current_pos] = [runner for runner in grid[current_pos] if runner != player]
    new_progress = move_progress(current_progress, total_steps, track_length)
    if skill_state is not None and skill_enabled(config, HIYUKI_ID) and player == HIYUKI_ID and NPC_ID in progress:
        record_hiyuki_npc_path_contact(
            movers=[player],
            progress=progress,
            track_length=track_length,
            path=forward_path_positions(current_progress, total_steps, track_length),
            skill_state=skill_state,
            trace=trace,
        )
    add_group_to_position(
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
    maybe_arm_aemeath_pending(
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
    config: RaceConfig,
    player: int,
    idx_in_cell: int,
    total_steps: int,
    rng: random.Random,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
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
        record_hiyuki_npc_path_contact(
            movers=movers,
            progress=progress,
            track_length=track_length,
            path=forward_path_positions(current_progress, total_steps, track_length),
            skill_state=skill_state,
            trace=trace,
        )
    add_group_to_position(
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
    maybe_arm_aemeath_pending(
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
    config: RaceConfig,
    player: int,
    total_steps: int,
    rng: random.Random,
    cantarella_state: int,
    cantarella_group: list[int],
    trace: TraceContext,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
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
            record_hiyuki_npc_path_contact(
                movers=movers,
                progress=progress,
                track_length=track_length,
                path=forward_path_positions(current_progress, 1, track_length),
                skill_state=skill_state,
                trace=trace,
            )
        add_group_to_position(
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
        maybe_arm_aemeath_pending(
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
            log_grid(trace, grid)

        if not group_mode:
            old_set = set(old_cell)
            if any(runner not in old_set for runner in grid[new_pos]):
                group_mode = True
                group = list(grid[new_pos])
                cantarella_state = 2
                if trace:
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
    *,
    active_player: int | None = None,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
    apply_effects: bool = True,
) -> None:
    core_add_group_to_position(
        grid,
        progress,
        movers,
        new_progress,
        rng,
        config,
        hooks=_effect_hooks(),
        active_player=active_player,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
        apply_effects=apply_effects,
    )


def apply_cell_effects(
    grid: dict[int, list[int]],
    progress: dict[int, int],
    movers: Sequence[int],
    pos: int,
    rng: random.Random,
    config: RaceConfig,
    *,
    active_player: int | None = None,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
) -> None:
    core_apply_cell_effects(
        grid,
        progress,
        movers,
        pos,
        rng,
        config,
        hooks=_effect_hooks(),
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
    config: RaceConfig,
    *,
    active_player: int | None = None,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
) -> None:
    core_move_group_due_to_cell_effect(
        grid,
        progress,
        movers,
        current_pos,
        delta,
        rng,
        config,
        hooks=_effect_hooks(),
        active_player=active_player,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
    )


def move_npc(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    npc_progress: int,
    rng: random.Random,
    trace: TraceContext,
    steps: int | None = None,
    skill_state: RaceSkillState | None = None,
    movement_state: RaceMovementState | None = None,
    ignore_waiting_stack: bool = False,
) -> int:
    return core_move_npc(
        grid=grid,
        progress=progress,
        config=config,
        npc_progress=npc_progress,
        rng=rng,
        trace=trace,
        steps=steps,
        skill_state=skill_state,
        movement_state=movement_state,
        ignore_waiting_stack=ignore_waiting_stack,
        helpers=_npc_helpers(),
    )


def settle_npc_end_of_round(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    runners: Sequence[int],
    npc_progress: int,
    track_length: int,
    trace: TraceContext,
) -> int:
    return core_settle_npc_end_of_round(
        grid=grid,
        progress=progress,
        runners=runners,
        npc_progress=npc_progress,
        track_length=track_length,
        trace=trace,
        helpers=_npc_helpers(),
    )


def apply_shuffle_cell_effect(
    grid: dict[int, list[int]],
    pos: int,
    rng: random.Random,
    *,
    trace: TraceContext = False,
) -> None:
    core_apply_shuffle_cell_effect(grid, pos, rng, hooks=_effect_hooks(), trace=trace)


def adjust_cell_effect_delta(
    active_player: int | None,
    delta: int,
    *,
    disabled_skills: frozenset[int] = frozenset(),
    skill_state: RaceSkillState | None = None,
    trace: TraceContext = False,
) -> int:
    return core_adjust_cell_effect_delta(
        active_player,
        delta,
        hooks=_effect_hooks(),
        disabled_skills=disabled_skills,
        skill_state=skill_state,
        trace=trace,
    )


def maybe_arm_aemeath_pending(
    *,
    movers: Sequence[int],
    start_progress: int,
    end_progress: int,
    moved_forward: bool,
    config: RaceConfig,
    skill_state: RaceSkillState | None,
    trace: TraceContext = False,
) -> None:
    if (
        AEMEATH_ID not in movers
        or skill_state is None
        or not skill_state.aemeath_available
        or skill_state.aemeath_ready
        or not skill_enabled(config, AEMEATH_ID)
        or not moved_forward
    ):
        return
    if start_progress < AEMEATH_TRIGGER_CELL and end_progress < AEMEATH_TRIGGER_CELL:
        return
    skill_state.aemeath_ready = True
    if trace:
        log_block(
            trace,
            f"{format_runner(AEMEATH_ID)}技能进入待判定状态：",
            f"经过格：{format_position(AEMEATH_TRIGGER_CELL)}",
            "效果：之后在自身主动前进结束后检查前方是否有角色",
        )


def maybe_trigger_aemeath_after_active_move(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    start_progress: int,
    action_had_forward_movement: bool,
    rng: random.Random,
    skill_state: RaceSkillState | None,
    movement_state: RaceMovementState | None = None,
    trace: TraceContext = False,
) -> None:
    core_maybe_trigger_aemeath_after_active_move(
        grid=grid,
        progress=progress,
        config=config,
        start_progress=start_progress,
        action_had_forward_movement=action_had_forward_movement,
        rng=rng,
        skill_state=skill_state,
        movement_state=movement_state,
        trace=trace,
        helpers=_skill_hook_helpers(),
        aemeath_trigger_cell=AEMEATH_TRIGGER_CELL,
    )


def maybe_trigger_luno_after_action(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    config: RaceConfig,
    skill_state: RaceSkillState | None,
    trace: TraceContext = False,
) -> None:
    core_maybe_trigger_luno_after_action(
        grid=grid,
        progress=progress,
        config=config,
        skill_state=skill_state,
        trace=trace,
        helpers=_skill_hook_helpers(),
        aemeath_trigger_cell=AEMEATH_TRIGGER_CELL,
    )


def nearest_runner_progress_ahead(
    *,
    progress: dict[int, int],
    from_progress: int,
    track_length: int,
    excluded: set[int],
) -> int | None:
    return core_nearest_runner_progress_ahead(
        progress=progress,
        from_progress=from_progress,
        track_length=track_length,
        excluded=excluded,
    )


def gather_runners_to_luno_cell(
    *,
    grid: dict[int, list[int]],
    progress: dict[int, int],
    ranking: Sequence[int],
    target_progress: int,
    track_length: int,
) -> None:
    core_gather_runners_to_luno_cell(
        grid=grid,
        progress=progress,
        ranking=ranking,
        target_progress=target_progress,
        track_length=track_length,
    )


def record_hiyuki_npc_path_contact(
    *,
    movers: Sequence[int],
    progress: dict[int, int],
    track_length: int,
    path: Iterable[int],
    skill_state: RaceSkillState | None,
    trace: TraceContext = False,
) -> None:
    core_record_hiyuki_npc_path_contact(
        movers=movers,
        progress=progress,
        track_length=track_length,
        path=path,
        skill_state=skill_state,
        trace=trace,
        helpers=_skill_hook_helpers(),
    )


def record_hiyuki_npc_destination_contact_legacy(
    arrivals: Sequence[int],
    destination_before: Sequence[int],
    skill_state: RaceSkillState | None,
    trace: TraceContext = False,
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
    if skill_state.hiyuki_bonus_steps > 0:
        if trace:
            log_block(
                trace,
                f"{format_runner(HIYUKI_ID)}技能不重复叠加：",
                f"原因：{reason}",
                "当前状态：已生效",
            )
        return
    skill_state.hiyuki_bonus_steps += 1
    if trace:
        log_block(
            trace,
            f"{format_runner(HIYUKI_ID)}技能触发：",
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
    skill_state: RaceSkillState | None = None,
    trace: TraceContext = False,
) -> None:
    core_maybe_trigger_player1_skill_after_action(
        grid=grid,
        progress=progress,
        actor=actor,
        track_length=track_length,
        rng=rng,
        disabled_skills=disabled_skills,
        skill_state=skill_state,
        trace=trace,
        helpers=_skill_hook_helpers(),
        jinhsi_reorder_chance=JINHSI_REORDER_CHANCE,
    )


def check_player2_skill(
    grid: dict[int, Sequence[int]],
    rng: random.Random,
    disabled_skills: frozenset[int] = frozenset(),
    skill_state: RaceSkillState | None = None,
    trace: TraceContext = False,
) -> bool:
    if not skill_enabled_from_set(disabled_skills, CHANGLI_ID):
        return False
    for cell in grid.values():
        if CHANGLI_ID in cell and cell.index(CHANGLI_ID) < len(cell) - 1:
            if trace:
                log_block(
                    trace,
                    f"{format_runner(CHANGLI_ID)}技能进入概率判定：",
                    f"格内顺序：{format_cell(cell)}",
                )
            if rng.random() <= CHANGLI_EXTRA_STEP_CHANCE:
                record_skill_success(skill_state, CHANGLI_ID)
                if trace:
                    log_block(trace, f"{format_runner(CHANGLI_ID)}技能触发：", "效果：下一轮固定最后行动")
                return True
            if trace:
                log_block(trace, f"{format_runner(CHANGLI_ID)}技能未触发：", "原因：概率判定失败")
            return False
    if trace:
        log_block(trace, f"{format_runner(CHANGLI_ID)}技能不判定：", "原因：当前不在同格最右侧之外")
    return False


def current_rank(runners: Sequence[int], progress: dict[int, int], grid: dict[int, Sequence[int]]) -> list[int]:
    selected = set(runners)
    cell_index: dict[int, int] = {}
    for cell in grid.values():
        for idx, runner in enumerate(cell):
            if runner != NPC_ID and runner in selected:
                cell_index[runner] = idx
    return sorted(runners, key=lambda runner: (-progress[runner], cell_index.get(runner, 9999)))


def simulate_stage(
    *,
    season: int,
    match_type: str,
    runners: Sequence[int],
    rng: random.Random,
    start_spec: str | None = None,
    track_length: int | None = None,
    initial_order: str | None = None,
    title: str | None = None,
) -> StageResult:
    return core_simulate_stage(
        season=season,
        match_type=match_type,
        runners=runners,
        rng=rng,
        build_race_config_fn=build_race_config,
        simulate_race_fn=simulate_race,
        start_spec=start_spec,
        track_length=track_length,
        initial_order=initial_order,
        title=title,
    )


def validate_champion_prediction_season(season: int) -> None:
    core_validate_champion_prediction_season(season)


def simulate_tournament(season: int, rng: random.Random) -> TournamentResult:
    return core_simulate_tournament(
        season,
        rng,
        season_runner_pool_fn=season_runner_pool,
        simulate_stage_fn=simulate_stage,
    )


def simulate_tournament_chunk(
    season: int,
    iterations: int,
    seed: int | None,
    *,
    start_index: int = 0,
    progress: ProgressBar | None = None,
) -> ChampionPredictionAccumulator:
    return core_simulate_tournament_chunk(
        season,
        iterations,
        seed,
        season_runner_pool_fn=season_runner_pool,
        simulate_tournament_fn=simulate_tournament,
        derive_seed_fn=derive_race_seed,
        progress_batch_size_fn=progress_batch_size,
        start_index=start_index,
        progress=progress,
    )


def simulate_tournament_chunk_from_tuple(
    args: tuple[int, int, int | None, int],
) -> ChampionPredictionAccumulator:
    season, iterations, seed, start_index = args
    return simulate_tournament_chunk(season, iterations, seed, start_index=start_index)


def run_monte_carlo(
    config: RaceConfig,
    iterations: int,
    *,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
    progress: ProgressBar | None = None,
) -> SimulationSummary:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if workers == 0:
        workers = mp.cpu_count()
    workers = max(1, min(workers, iterations))

    owned_progress: ProgressBar | None = None
    if progress is None and show_progress:
        owned_progress = ProgressBar(iterations, "模拟进度")
        progress = owned_progress

    try:
        if workers == 1:
            acc = simulate_chunk(config, iterations, seed, progress=progress)
            return acc.to_summary(config)

        chunk_sizes = split_iterations(iterations, parallel_task_count(iterations, workers))
        chunk_args: list[tuple[RaceConfig, int, int | None, int]] = []
        start_index = 0
        for chunk_size in chunk_sizes:
            if chunk_size > 0:
                chunk_args.append((config, chunk_size, seed, start_index))
            start_index += chunk_size
        acc = MonteCarloAccumulator(config.runners, config.qualify_cutoff)
        with mp.Pool(processes=workers) as pool:
            if progress is None:
                parts = pool.map(simulate_chunk_from_tuple, chunk_args)
                for part in parts:
                    acc.merge(part)
            else:
                for part in pool.imap_unordered(simulate_chunk_from_tuple, chunk_args):
                    acc.merge(part)
                    progress.advance(part.iterations)
        return acc.to_summary(config)
    finally:
        if owned_progress is not None:
            owned_progress.close()


def run_champion_prediction_monte_carlo(
    season: int,
    iterations: int,
    *,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
) -> ChampionPredictionSummary:
    validate_champion_prediction_season(season)
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if workers == 0:
        workers = mp.cpu_count()
    workers = max(1, min(workers, iterations))

    start_time = time.perf_counter()
    owned_progress: ProgressBar | None = None
    progress: ProgressBar | None = None
    if show_progress:
        owned_progress = ProgressBar(iterations, "冠军预测进度")
        progress = owned_progress

    try:
        if workers == 1:
            acc = simulate_tournament_chunk(season, iterations, seed, progress=progress)
        else:
            chunk_sizes = split_iterations(iterations, parallel_task_count(iterations, workers))
            chunk_args: list[tuple[int, int, int | None, int]] = []
            start_index = 0
            for chunk_size in chunk_sizes:
                if chunk_size > 0:
                    chunk_args.append((season, chunk_size, seed, start_index))
                start_index += chunk_size
            acc = ChampionPredictionAccumulator(season_runner_pool(season))
            with mp.Pool(processes=workers) as pool:
                if progress is None:
                    parts = pool.map(simulate_tournament_chunk_from_tuple, chunk_args)
                    for part in parts:
                        acc.merge(part)
                else:
                    for part in pool.imap_unordered(simulate_tournament_chunk_from_tuple, chunk_args):
                        acc.merge(part)
                        progress.advance(part.iterations)
        return acc.to_summary(season=season, elapsed_seconds=time.perf_counter() - start_time)
    finally:
        if owned_progress is not None:
            owned_progress.close()


def run_skill_ablation(
    config: RaceConfig,
    iterations: int,
    *,
    targets: Sequence[int] | None = None,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
) -> SkillAblationSummary:
    evaluated = resolve_skill_ablation_runners(config.runners, targets)

    total_start = time.perf_counter()
    if show_progress:
        emit_progress_overview(
            format_skill_ablation_overview_lines(
                config,
                iterations=iterations,
                scenario_count=len(evaluated) + 1,
                total_simulated_races=iterations * (len(evaluated) + 1),
                pending=True,
            )
        )
    progress = ProgressBar(iterations * (len(evaluated) + 1), "技能消融", enabled=show_progress) if show_progress else None
    base_start = time.perf_counter()
    try:
        base_summary = with_elapsed(
            run_monte_carlo(config, iterations, seed=seed, workers=workers, progress=progress),
            time.perf_counter() - base_start,
        )
        base_rows = {row.runner: row for row in base_summary.rows}

        seed_rng = random.Random(seed)
        rows: list[SkillAblationRow] = []
        for runner in evaluated:
            disabled_seed = seed_rng.randrange(1, 2**63) if seed is not None else None
            disabled_config = replace(
                config,
                disabled_skills=frozenset(set(config.disabled_skills) | {runner}),
            )
            disabled_summary = run_monte_carlo(
                disabled_config,
                iterations,
                seed=disabled_seed,
                workers=workers,
                progress=progress,
            )
            disabled_rows = {row.runner: row for row in disabled_summary.rows}
            enabled_row = base_rows[runner]
            disabled_row = disabled_rows[runner]
            rows.append(
                SkillAblationRow(
                    runner=runner,
                    name=enabled_row.name,
                    enabled_win_rate=enabled_row.win_rate,
                    disabled_win_rate=disabled_row.win_rate,
                    net_win_rate=enabled_row.win_rate - disabled_row.win_rate,
                    skill_average_success_count=enabled_row.skill_average_success_count,
                    skill_marginal_win_rate=enabled_row.skill_marginal_win_rate,
                    success_distribution=enabled_row.skill_success_distribution,
                )
            )

        return SkillAblationSummary(
            iterations=iterations,
            total_simulated_races=iterations * (len(evaluated) + 1),
            base_summary=base_summary,
            rows=tuple(rows),
            elapsed_seconds=time.perf_counter() - total_start,
        )
    finally:
        if progress is not None:
            progress.close()


def validate_season_roster_scan_args(args: argparse.Namespace) -> tuple[int, ...]:
    if args.field_size is None:
        raise ValueError("--field-size is required when --season-roster-scan is enabled")
    if args.runners:
        raise ValueError("--season-roster-scan enumerates the season roster automatically; do not combine it with --runners")
    if args.trace or args.trace_log:
        raise ValueError("--season-roster-scan cannot be combined with --trace or --trace-log")
    if args.skill_ablation or args.skill_ablation_runners or args.skill_ablation_detail:
        raise ValueError("--season-roster-scan cannot be combined with skill ablation options")
    if args.initial_order and args.initial_order not in {"random", "start"}:
        raise ValueError("--season-roster-scan only supports --initial-order random or --initial-order start")
    if not args.start:
        raise ValueError("--start is required; pass a reusable start such as '1:*'")

    roster = season_runner_pool(args.season)
    if args.field_size < 1 or args.field_size > len(roster):
        raise ValueError(f"--field-size must be between 1 and {len(roster)} for season {args.season}")

    start_cells, random_start_position = parse_start_layout(args.start)
    if random_start_position is None or start_cells:
        raise ValueError("--season-roster-scan currently requires a reusable '*' start such as '1:*' or '-1:*'")
    track_length = args.track_length or int(season_rules(args.season)["track_length"])
    validate_start_position(random_start_position, track_length)
    return roster


def run_season_roster_scan_task(args: tuple[RaceConfig, int, int | None]) -> SimulationSummary:
    config, iterations, seed = args
    return run_monte_carlo(config, iterations, seed=seed, workers=1)


def season_roster_combination_count(season: int, field_size: int) -> int:
    roster = season_runner_pool(season)
    if field_size < 0 or field_size > len(roster):
        raise ValueError(f"field_size must be between 0 and {len(roster)} for season {season}")
    return math.comb(len(roster), field_size)


def run_season_roster_scan(args: argparse.Namespace, *, show_progress: bool = False) -> SeasonRosterScanSummary:
    roster = validate_season_roster_scan_args(args)
    combo_list = list(combinations(roster, args.field_size))
    total_start = time.perf_counter()
    acc = SeasonRosterScanAccumulator(roster)
    seed_rng = random.Random(args.seed)
    task_args = [
        (
            build_config_from_args(args, runners_override=combo),
            args.iterations,
            seed_rng.randrange(1, 2**63) if args.seed is not None else None,
        )
        for combo in combo_list
    ]

    workers = args.workers
    if workers == 0:
        workers = mp.cpu_count()
    workers = max(1, min(workers, len(task_args)))

    template_config = build_config_from_args(args, runners_override=combo_list[0])
    if show_progress:
        emit_progress_overview(
            format_season_roster_scan_overview_lines(
                season=args.season,
                roster=roster,
                field_size=args.field_size,
                qualify_cutoff=template_config.qualify_cutoff,
                start_spec=args.start,
                initial_order_mode=template_config.initial_order_mode,
                combination_count=len(combo_list),
                iterations_per_combination=args.iterations,
                total_simulated_races=len(combo_list) * args.iterations,
                track_length=template_config.track_length,
                pending=True,
            )
        )
    progress = ProgressBar(len(combo_list) * args.iterations, "阵容遍历", enabled=show_progress) if show_progress else None

    try:
        if workers == 1:
            for config, iterations, seed in task_args:
                acc.add_summary(
                    run_monte_carlo(
                        config,
                        iterations,
                        seed=seed,
                        workers=1,
                        progress=progress,
                    )
                )
        else:
            chunksize = max(1, len(task_args) // (workers * 4))
            with mp.Pool(processes=workers) as pool:
                for summary in pool.imap_unordered(run_season_roster_scan_task, task_args, chunksize=chunksize):
                    acc.add_summary(summary)
                    if progress is not None:
                        progress.advance(summary.iterations)

        return acc.to_summary(
            season=args.season,
            field_size=args.field_size,
            qualify_cutoff=template_config.qualify_cutoff,
            iterations_per_combination=args.iterations,
            combination_count=len(combo_list),
            start_spec=args.start,
            track_length=template_config.track_length,
            initial_order_mode=template_config.initial_order_mode,
            elapsed_seconds=time.perf_counter() - total_start,
        )
    finally:
        if progress is not None:
            progress.close()


def resolve_skill_ablation_runners(
    selected_runners: Sequence[int],
    requested_runners: Sequence[int] | None,
) -> tuple[int, ...]:
    selected = set(selected_runners)
    if requested_runners is None:
        runners = tuple(runner for runner in selected_runners if runner in SKILL_RUNNERS)
    else:
        runners = tuple(requested_runners)
        if len(set(runners)) != len(runners):
            raise ValueError("skill ablation runners contain duplicates")
        missing = set(runners) - selected
        if missing:
            raise ValueError(f"skill ablation runners are not selected: {format_runner_list(sorted(missing))}")
    without_skills = [runner for runner in runners if runner not in SKILL_RUNNERS]
    if without_skills:
        raise ValueError(f"runners do not have implemented skill ablation: {format_runner_list(without_skills)}")
    if not runners:
        raise ValueError("no selected runners have implemented skills to ablate")
    return runners


def derive_race_seed(master_seed: int, race_index: int) -> int:
    value = (master_seed & RNG_SEED_MASK) + ((race_index + 1) * 0x9E3779B97F4A7C15)
    value &= RNG_SEED_MASK
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & RNG_SEED_MASK
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & RNG_SEED_MASK
    value ^= value >> 31
    return value or 1


def simulate_chunk_from_tuple(args: tuple[RaceConfig, int, int | None, int]) -> MonteCarloAccumulator:
    config, iterations, seed, start_index = args
    return simulate_chunk(config, iterations, seed, start_index=start_index)


def simulate_chunk(
    config: RaceConfig,
    iterations: int,
    seed: int | None,
    *,
    start_index: int = 0,
    progress: ProgressBar | None = None,
) -> MonteCarloAccumulator:
    chunk_rng = random.Random(seed)
    race_rng = random.Random()
    acc = MonteCarloAccumulator(config.runners, config.qualify_cutoff)
    progress_batch = progress_batch_size(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            current_rng = chunk_rng
        else:
            race_rng.seed(derive_race_seed(seed, start_index + index))
            current_rng = race_rng
        acc.add(simulate_race(config, current_rng))
        pending_progress += 1
        if progress is not None and (pending_progress >= progress_batch or index == iterations - 1):
            progress.advance(pending_progress)
            pending_progress = 0
    return acc


def parallel_task_count(iterations: int, workers: int) -> int:
    return max(1, min(iterations, workers * 8))


def split_iterations(iterations: int, chunk_count: int) -> list[int]:
    base, remainder = divmod(iterations, chunk_count)
    return [base + (1 if i < remainder else 0) for i in range(chunk_count)]


def progress_batch_size(iterations: int) -> int:
    if iterations <= 200:
        return 1
    return max(1, min(5_000, iterations // 200))


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


def parse_runner_tokens(
    tokens: Sequence[str] | None,
    rng: random.Random | None = None,
    runner_pool: Sequence[int] | None = None,
) -> tuple[int, ...] | None:
    if not tokens:
        return None
    pool = tuple(runner_pool) if runner_pool is not None else tuple(sorted(runner for runner in RUNNER_NAMES if runner > 0))
    random_count = parse_random_runner_count(tokens, pool_size=len(pool))
    if random_count is not None:
        selection_rng = rng or random.Random()
        return tuple(sorted(selection_rng.sample(pool, random_count)))
    runners: list[int] = []
    for token in tokens:
        for part in token.split(","):
            if part.strip():
                runners.append(parse_runner(part))
    if len(set(runners)) != len(runners):
        raise ValueError("selected runners contain duplicates")
    return tuple(runners)


def parse_random_runner_count(tokens: Sequence[str], pool_size: int | None = None) -> int | None:
    parts = [part.strip() for token in tokens for part in token.split(",") if part.strip()]
    if not parts:
        return None
    first = parts[0]
    normalized = first.lower()
    if normalized in RANDOM_RUNNER_ALIASES:
        count = 6
    elif ":" in normalized or "=" in normalized:
        separator = ":" if ":" in normalized else "="
        prefix, count_text = normalized.split(separator, 1)
        if prefix not in RANDOM_RUNNER_ALIASES:
            return None
        if not count_text.isdigit():
            raise ValueError(f"invalid random runner count: {first}")
        count = int(count_text)
    else:
        return None
    if len(parts) != 1:
        raise ValueError("random runner selection cannot be mixed with explicit runners")
    available_pool_size = pool_size if pool_size is not None else sum(1 for runner in RUNNER_NAMES if runner > 0)
    if count < 1 or count > available_pool_size:
        raise ValueError(f"random runner count must be 1..{available_pool_size}")
    return count


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


def resolve_match_type_rule(args: argparse.Namespace) -> MatchTypeRule | None:
    return core_resolve_match_type_rule(
        season=args.season,
        match_type=getattr(args, "match_type", None),
        get_match_type_rule_fn=get_match_type_rule,
    )


def build_race_config(
    *,
    season: int,
    runners: Sequence[int],
    start_spec: str,
    track_length: int | None,
    initial_order: str | None,
    qualify_cutoff: int,
    match_rule: MatchTypeRule | None = None,
    name: str | None = None,
) -> RaceConfig:
    return core_build_race_config(
        season=season,
        runners=runners,
        start_spec=start_spec,
        track_length=track_length,
        initial_order=initial_order,
        qualify_cutoff=qualify_cutoff,
        race_config_factory=RaceConfig,
        season_rules_fn=season_rules,
        parse_start_layout_fn=parse_start_layout,
        validate_start_position_fn=validate_start_position,
        empty_grid_fn=empty_grid,
        make_start_grid_fn=make_start_grid,
        validate_fixed_start_fn=validate_fixed_start,
        validate_qualify_cutoff_fn=validate_qualify_cutoff,
        parse_runner_tokens_fn=parse_runner_tokens,
        validate_same_runners_fn=validate_same_runners,
        match_rule=match_rule,
        name=name,
    )


def build_config_from_args(
    args: argparse.Namespace,
    *,
    runners_override: Sequence[int] | None = None,
) -> RaceConfig:
    season = args.season
    runner_pool = season_runner_pool(season)
    runners = (
        tuple(runners_override)
        if runners_override is not None
        else parse_runner_tokens(args.runners, rng=random.Random(args.seed), runner_pool=runner_pool)
    )
    match_rule = resolve_match_type_rule(args)
    if match_rule is None:
        if not args.start:
            raise ValueError("--start is required; pass a custom start grid such as '1:*' or '-3:2;-2:1,4;1:5'")
        start_spec = args.start
        qualify_cutoff = resolve_qualify_cutoff(args)
    else:
        if runners is None:
            raise ValueError("--runners is required when --match-type is used")
        start_spec = args.start or resolve_match_start_spec(match_rule, runners)
        qualify_cutoff = effective_qualify_cutoff(match_rule, len(runners))
    return build_race_config(
        season=season,
        runners=runners or (),
        start_spec=start_spec,
        track_length=args.track_length,
        initial_order=args.initial_order,
        qualify_cutoff=qualify_cutoff,
        match_rule=match_rule,
    )


def default_initial_order_mode(grid: dict[int, Sequence[int]], random_start_position: int | None) -> str:
    return core_default_initial_order_mode(grid, random_start_position)


def summary_to_dict(summary: SimulationSummary) -> dict[str, object]:
    return core_summary_to_dict(
        summary,
        races_per_second_fn=races_per_second,
        format_start_overview_fn=format_start_overview,
    )


def skill_ablation_to_dict(
    summary: SkillAblationSummary,
    *,
    include_detail: bool = False,
) -> dict[str, object]:
    return core_skill_ablation_to_dict(summary, include_detail=include_detail)


def season_roster_scan_to_dict(summary: SeasonRosterScanSummary) -> dict[str, object]:
    return core_season_roster_scan_to_dict(summary)


def stage_result_to_dict(result: StageResult) -> dict[str, object]:
    return core_stage_result_to_dict(result)


def tournament_result_to_dict(result: TournamentResult) -> dict[str, object]:
    return core_tournament_result_to_dict(result)


def champion_prediction_races_per_second(summary: ChampionPredictionSummary) -> float | None:
    return core_champion_prediction_races_per_second(summary)


def champion_prediction_to_dict(summary: ChampionPredictionSummary) -> dict[str, object]:
    return core_champion_prediction_to_dict(summary)


def format_summary(summary: SimulationSummary, sort_by_win_rate: bool = True) -> str:
    return core_format_summary(
        summary,
        sort_by_win_rate=sort_by_win_rate,
        format_runner_fn=format_runner,
        display_width_fn=display_width,
        format_simulation_overview_lines_fn=format_simulation_overview_lines,
        format_table_row_fn=format_table_row,
        format_table_separator_fn=format_table_separator,
        races_per_second_fn=races_per_second,
    )


def format_season_roster_scan_summary(summary: SeasonRosterScanSummary) -> str:
    return core_format_season_roster_scan_summary(
        summary,
        format_runner_fn=format_runner,
        display_width_fn=display_width,
        format_season_roster_scan_overview_lines_fn=format_season_roster_scan_overview_lines,
        format_table_row_fn=format_table_row,
        format_table_separator_fn=format_table_separator,
    )


def format_tournament_result(result: TournamentResult) -> str:
    return core_format_tournament_result(result)


def format_champion_prediction_summary(summary: ChampionPredictionSummary) -> str:
    return core_format_champion_prediction_summary(summary)


def format_skill_ablation_summary(summary: SkillAblationSummary, *, detail: bool = False) -> str:
    return core_format_skill_ablation_summary(
        summary,
        detail=detail,
        format_runner_fn=format_runner,
        display_width_fn=display_width,
        format_table_row_fn=format_table_row,
        format_table_separator_fn=format_table_separator,
        format_elapsed_fn=format_elapsed,
        format_rate_fn=format_rate,
    )


def skill_ablation_races_per_second(summary: SkillAblationSummary) -> float | None:
    return core_skill_ablation_races_per_second(summary)


def season_roster_scan_races_per_second(summary: SeasonRosterScanSummary) -> float | None:
    return core_season_roster_scan_races_per_second(summary)


def with_elapsed(summary: SimulationSummary, elapsed_seconds: float) -> SimulationSummary:
    return SimulationSummary(
        iterations=summary.iterations,
        config=summary.config,
        rows=summary.rows,
        elapsed_seconds=elapsed_seconds,
    )


def races_per_second(summary: SimulationSummary) -> float | None:
    if summary.elapsed_seconds is None or summary.elapsed_seconds <= 0:
        return None
    return summary.iterations / summary.elapsed_seconds


def format_elapsed(elapsed_seconds: float | None) -> str:
    if elapsed_seconds is None:
        return "未统计"
    if elapsed_seconds < 1:
        return f"{elapsed_seconds * 1000:.0f} ms"
    return f"{elapsed_seconds:.2f} 秒"


def format_rate(rate: float | None) -> str:
    if rate is None:
        return "未统计"
    return f"{rate:,.0f} 局/秒"


def format_runtime_status_line(label: str, value: str) -> str:
    return f"{label}：{value}"


def format_qualify_label(qualify_cutoff: int) -> str:
    return f"前{qualify_cutoff}名"


def format_simulation_overview_lines(
    config: RaceConfig,
    iterations: int,
    *,
    elapsed_seconds: float | None = None,
    rate: float | None = None,
    pending: bool = False,
) -> list[str]:
    lines = [
        format_runtime_status_line("赛制", config.name),
        format_runtime_status_line("赛季", f"第{config.season}季"),
        format_runtime_status_line("登场角色", format_runner_list(config.runners)),
        format_runtime_status_line("模拟次数", f"{iterations:,}"),
        format_runtime_status_line("赛道长度", f"{config.track_length}格"),
        format_runtime_status_line("用时", "进行中" if pending else format_elapsed(elapsed_seconds)),
        format_runtime_status_line("速度", "计算中" if pending else format_rate(rate)),
    ]
    if config.show_qualify_stats:
        lines.insert(5, format_runtime_status_line("晋级统计", format_qualify_label(config.qualify_cutoff)))
    if config.random_start_stack:
        lines.append(format_runtime_status_line("起跑配置", format_random_start_layout(config.random_start_position)))
    elif config.start_grid:
        lines.append(format_runtime_status_line("自定义站位", format_start_layout(config.start_grid)))
    return lines


def format_skill_ablation_overview_lines(
    config: RaceConfig,
    *,
    iterations: int,
    scenario_count: int,
    total_simulated_races: int,
    elapsed_seconds: float | None = None,
    rate: float | None = None,
    pending: bool = False,
) -> list[str]:
    lines = [
        format_runtime_status_line("赛制", config.name),
        format_runtime_status_line("赛季", f"第{config.season}季"),
        format_runtime_status_line("登场角色", format_runner_list(config.runners)),
        format_runtime_status_line("每组模拟", f"{iterations:,}局"),
        format_runtime_status_line("消融组数", f"{scenario_count - 1}个角色 + 1个技能全开基准"),
        format_runtime_status_line("总模拟局数", f"{total_simulated_races:,}局"),
        format_runtime_status_line("赛道长度", f"{config.track_length}格"),
        format_runtime_status_line("用时", "进行中" if pending else format_elapsed(elapsed_seconds)),
        format_runtime_status_line("速度", "计算中" if pending else format_rate(rate)),
    ]
    if config.show_qualify_stats:
        lines.insert(7, format_runtime_status_line("晋级统计", format_qualify_label(config.qualify_cutoff)))
    if config.random_start_stack:
        lines.append(format_runtime_status_line("起跑配置", format_random_start_layout(config.random_start_position)))
    elif config.start_grid:
        lines.append(format_runtime_status_line("自定义站位", format_start_layout(config.start_grid)))
    return lines


def format_season_roster_scan_overview_lines(
    *,
    season: int,
    roster: Sequence[int],
    field_size: int,
    qualify_cutoff: int,
    start_spec: str,
    initial_order_mode: str,
    combination_count: int,
    iterations_per_combination: int,
    total_simulated_races: int,
    track_length: int,
    elapsed_seconds: float | None = None,
    rate: float | None = None,
    pending: bool = False,
) -> list[str]:
    return [
        "赛季角色池遍历统计：",
        format_runtime_status_line("赛季", f"第{season}季"),
        format_runtime_status_line("角色池", f"{len(roster)}人（{format_runner_list(roster)}）"),
        format_runtime_status_line("每组人数", f"{field_size}人"),
        format_runtime_status_line("晋级统计", format_qualify_label(qualify_cutoff)),
        format_runtime_status_line("起点配置", start_spec),
        format_runtime_status_line("首轮顺序", format_initial_order_mode(initial_order_mode)),
        format_runtime_status_line("组合数", f"{combination_count:,}组"),
        format_runtime_status_line("每组模拟", f"{iterations_per_combination:,}局"),
        format_runtime_status_line("总模拟局数", f"{total_simulated_races:,}局"),
        format_runtime_status_line("赛道长度", f"{track_length}格"),
        format_runtime_status_line("用时", "进行中" if pending else format_elapsed(elapsed_seconds)),
        format_runtime_status_line("速度", "计算中" if pending else format_rate(rate)),
    ]


def emit_progress_overview(lines: Sequence[str], *, stream: TextIO | None = None) -> None:
    output = stream or sys.stderr
    output.write("\n".join(lines) + "\n")
    output.flush()


def format_table_row(cells: Sequence[str], widths: Sequence[int], aligns: Sequence[str]) -> str:
    parts = [
        pad_display_width(cell, width, align=align)
        for cell, width, align in zip(cells, widths, aligns, strict=True)
    ]
    return "  ".join(parts)


def format_table_separator(widths: Sequence[int]) -> str:
    return "  ".join("-" * width for width in widths)


def pad_display_width(text: str, width: int, *, align: str = "left") -> str:
    padding = max(0, width - display_width(text))
    if align == "right":
        return " " * padding + text
    if align == "left":
        return text + " " * padding
    raise ValueError(f"unknown alignment: {align}")


def display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def format_runner_list(runners: Iterable[int]) -> str:
    return ", ".join(format_runner(runner) for runner in runners)


def format_runner_arrow_list(runners: Iterable[int]) -> str:
    return " -> ".join(format_runner(runner) for runner in runners)


def format_runner(runner: int) -> str:
    if runner == NPC_ID:
        return "NPC"
    return RUNNER_NAMES.get(runner, str(runner))


def format_initial_order_mode(mode: str) -> str:
    labels = {
        "start": "按起点顺序",
        "random": "随机",
        "fixed": "固定顺序",
    }
    return labels.get(mode, mode)


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


def format_start_layout(start_grid: dict[int, Sequence[int]]) -> str:
    parts = []
    for pos, cell in sorted(start_grid.items()):
        if cell:
            parts.append(f"{format_position(pos)}：{format_cell(cell)}")
    return "；".join(parts) if parts else "无"


def format_random_start_layout(position: int) -> str:
    return f"{format_position(position)}（全部登场角色同格，每局随机堆叠顺序）"


def format_start_overview(config: RaceConfig) -> str:
    if config.random_start_stack:
        return format_random_start_layout(config.random_start_position)
    return format_start_layout(config.start_grid)


def log(enabled: TraceContext, message: str) -> None:
    if not enabled:
        return
    if hasattr(enabled, "write_line"):
        enabled.write_line(message)
    else:
        print(message)


def log_timing(enabled: TraceContext, timing: str, message: str) -> None:
    if not enabled:
        return
    log(enabled, f"【判定时机：{timing}】")
    log(enabled, f"  {message}")
    log(enabled, "")


def log_rank_decision(enabled: TraceContext, ranking: Sequence[int], npc_rank_active: bool) -> None:
    if not enabled:
        return
    log_block(
        enabled,
        "当前名次判断：",
        f"NPC参与排名：{'是' if npc_rank_active else '否'}",
        f"名次（前→后）：{format_runner_arrow_list(ranking)}",
        f"当前最后一名：{format_runner(ranking[-1])}",
    )


def log_block(enabled: TraceContext, title: str, *lines: str) -> None:
    if not enabled:
        return
    log(enabled, title)
    for line in lines:
        log(enabled, f"  {line}")
    log(enabled, "")


def log_grid(
    enabled: TraceContext,
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


def _effect_hooks() -> EffectHooks:
    global _EFFECT_HOOKS
    if _EFFECT_HOOKS is None:
        _EFFECT_HOOKS = EffectHooks(
            record_movement=record_movement,
            record_hiyuki_npc_path_contact=record_hiyuki_npc_path_contact,
            maybe_arm_aemeath_pending=maybe_arm_aemeath_pending,
            format_position=format_position,
            format_cell=format_cell,
            format_runner=format_runner,
            log_block=log_block,
            log_timing=log_timing,
        )
    return _EFFECT_HOOKS


def _npc_helpers() -> NPCHelpers:
    global _NPC_HELPERS
    if _NPC_HELPERS is None:
        _NPC_HELPERS = NPCHelpers(
            apply_cell_effects=apply_cell_effects,
            current_rank=current_rank,
            format_cell=format_cell,
            format_position=format_position,
            format_runner=format_runner,
            log_block=log_block,
            record_hiyuki_npc_path_contact=record_hiyuki_npc_path_contact,
        )
    return _NPC_HELPERS


def _post_action_helpers() -> PostActionHelpers:
    global _POST_ACTION_HELPERS
    if _POST_ACTION_HELPERS is None:
        _POST_ACTION_HELPERS = PostActionHelpers(
            current_rank=current_rank,
            format_runner=format_runner,
            log_block=log_block,
            log_rank_decision=log_rank_decision,
            log_timing=log_timing,
            maybe_trigger_aemeath_after_active_move=maybe_trigger_aemeath_after_active_move,
            maybe_trigger_luno_after_action=maybe_trigger_luno_after_action,
            maybe_trigger_player1_skill_after_action=maybe_trigger_player1_skill_after_action,
            rank_scope=rank_scope,
        )
    return _POST_ACTION_HELPERS


def _skill_hook_helpers() -> SkillHookHelpers:
    global _SKILL_HOOK_HELPERS
    if _SKILL_HOOK_HELPERS is None:
        _SKILL_HOOK_HELPERS = SkillHookHelpers(
            add_group_to_position=add_group_to_position,
            current_rank=current_rank,
            format_cell=format_cell,
            format_position=format_position,
            format_runner=format_runner,
            log_block=log_block,
            log_timing=log_timing,
        )
    return _SKILL_HOOK_HELPERS


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulator for Wuthering Waves Cubie Derby.",
    )
    parser.add_argument("-n", "--iterations", type=int, default=100_000, help="number of races to simulate")
    parser.add_argument("--season", type=int, choices=[1, 2], default=1, help="season ruleset")
    parser.add_argument(
        "--match-type",
        help=(
            "season-aware stage rules, e.g. "
            + ", ".join(match_type_choices())
            + "; Chinese aliases are also supported"
        ),
    )
    parser.add_argument(
        "--champion-prediction",
        choices=("random", "monte-carlo"),
        help="run a full season tournament instead of a single-stage simulation",
    )
    parser.add_argument(
        "--season-roster-scan",
        action="store_true",
        help="enumerate every same-size combination from the selected season roster and aggregate the results",
    )
    parser.add_argument(
        "--field-size",
        type=int,
        help="lineup size used by --season-roster-scan, e.g. 6 for all 6-runner combinations",
    )
    parser.add_argument(
        "--runners",
        nargs="+",
        help="runner ids/names, e.g. --runners 3 4 8 10; use 'random' or 'random:6' to sample runners",
    )
    parser.add_argument(
        "--qualify-cutoff",
        type=int,
        default=4,
        help="count finishes within the top N as qualifying when computing 晋级率; default is 4",
    )
    parser.add_argument("--track-length", "--lap-length", dest="track_length", type=int, help="override lap length")
    parser.add_argument(
        "--start",
        help=(
            "custom start grid, e.g. '-3:10;-2:4,3;1:8'. "
            "Use '1:*' to randomly stack all runners in one cell."
        ),
    )
    parser.add_argument(
        "--initial-order",
        help="custom first-round order: 'random', 'start', or comma-separated runner ids",
    )
    parser.add_argument("--seed", type=int, help="random seed for reproducible output")
    parser.add_argument("--workers", "--worker", dest="workers", type=int, default=1, help="parallel workers; use 0 for CPU count")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--trace", action="store_true", help="print one traced race and exit")
    parser.add_argument("--trace-log", help="write one traced race to this log file and exit")
    parser.add_argument("--skill-ablation", action="store_true", help="run skill on/off ablation statistics")
    parser.add_argument(
        "--skill-ablation-runners",
        nargs="+",
        help="runner ids/names to ablate; defaults to all selected runners with implemented skills",
    )
    parser.add_argument(
        "--skill-ablation-detail",
        action="store_true",
        help="include skill success-count distribution in ablation output",
    )
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
    ablation_summary: SkillAblationSummary | None = None
    season_scan_summary: SeasonRosterScanSummary | None = None
    show_progress = sys.stderr.isatty() and not args.json
    try:
        if args.champion_prediction:
            if args.season_roster_scan:
                raise ValueError("--champion-prediction cannot be combined with --season-roster-scan")
            if args.skill_ablation:
                raise ValueError("--champion-prediction cannot be combined with --skill-ablation")
            if args.trace or args.trace_log:
                raise ValueError("--champion-prediction does not support trace output")
            if args.runners is not None:
                raise ValueError("--champion-prediction chooses the season roster automatically; do not pass --runners")
            if args.start or args.initial_order:
                raise ValueError("--champion-prediction uses stage rules automatically; do not pass --start or --initial-order")
            if args.match_type:
                raise ValueError("--champion-prediction already controls the full tournament; do not combine it with --match-type")
            validate_champion_prediction_season(args.season)
            if args.champion_prediction == "random":
                start_time = time.perf_counter()
                tournament = replace(
                    simulate_tournament(args.season, random.Random(args.seed)),
                    elapsed_seconds=time.perf_counter() - start_time,
                )
                if args.json:
                    print(json.dumps(tournament_result_to_dict(tournament), ensure_ascii=False, indent=2))
                else:
                    print(format_tournament_result(tournament))
                return 0
            champion_summary = run_champion_prediction_monte_carlo(
                args.season,
                args.iterations,
                seed=args.seed,
                workers=args.workers,
                show_progress=show_progress,
            )
            if args.json:
                print(json.dumps(champion_prediction_to_dict(champion_summary), ensure_ascii=False, indent=2))
            else:
                print(format_champion_prediction_summary(champion_summary))
            return 0
        if args.season_roster_scan:
            if args.match_type:
                raise ValueError("--match-type cannot be combined with --season-roster-scan")
            season_scan_summary = run_season_roster_scan(args, show_progress=show_progress)
            if args.json:
                print(json.dumps(season_roster_scan_to_dict(season_scan_summary), ensure_ascii=False, indent=2))
            else:
                print(format_season_roster_scan_summary(season_scan_summary))
            return 0
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
        if args.skill_ablation:
            targets = parse_runner_tokens(args.skill_ablation_runners)
            ablation_summary = run_skill_ablation(
                config,
                args.iterations,
                targets=targets,
                seed=args.seed,
                workers=args.workers,
                show_progress=show_progress,
            )
            summary = ablation_summary.base_summary
        else:
            start_time = time.perf_counter()
            if show_progress:
                emit_progress_overview(
                    format_simulation_overview_lines(
                        config,
                        args.iterations,
                        pending=True,
                    )
                )
            summary = run_monte_carlo(
                config,
                args.iterations,
                seed=args.seed,
                workers=args.workers,
                show_progress=show_progress,
            )
            summary = with_elapsed(summary, time.perf_counter() - start_time)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    if args.json:
        data = summary_to_dict(summary)
        if ablation_summary is not None:
            data["skill_ablation"] = skill_ablation_to_dict(
                ablation_summary,
                include_detail=args.skill_ablation_detail,
            )
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        text = format_summary(summary)
        if ablation_summary is not None:
            text += "\n\n" + format_skill_ablation_summary(
                ablation_summary,
                detail=args.skill_ablation_detail,
            )
        print(text)
    return 0


def trace_result_to_dict(result: RaceResult) -> dict[str, object]:
    movement_stats = [
        {
            "runner": runner,
            "name": format_runner(runner),
            "total_forward_steps": total_steps,
            "carried_forward_steps": carried_steps,
            "lazy_rate": carried_steps / total_steps if total_steps else 0.0,
        }
        for runner, total_steps, carried_steps in sorted(
            result.movement_stats,
            key=lambda item: result.ranking.index(item[0]) if item[0] in result.ranking else len(result.ranking),
        )
    ]
    return {
        "winner": format_runner(result.winner),
        "winner_id": result.winner,
        "ranking": [format_runner(runner) for runner in result.ranking],
        "ranking_ids": list(result.ranking),
        "second_position": result.second_position,
        "winner_margin": result.winner_margin,
        "winner_lazy_stats": {
            "carried_forward_steps": result.winner_carried_steps,
            "total_forward_steps": result.winner_total_steps,
            "lazy_rate": (
                result.winner_carried_steps / result.winner_total_steps
                if result.winner_total_steps
                else 0.0
            ),
        },
        "movement_stats": movement_stats,
        "skill_success_counts": {
            format_runner(runner): count for runner, count in result.skill_success_counts
        },
        "skill_success_count_ids": dict(result.skill_success_counts),
    }


if __name__ == "__main__":
    raise SystemExit(main())
