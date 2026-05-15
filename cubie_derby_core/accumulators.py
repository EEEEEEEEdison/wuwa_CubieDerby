from __future__ import annotations

import math
from typing import Any, Callable, Sequence


RunnerNameLookup = dict[int, str]
RunnerSummaryFactory = Callable[..., Any]
SeasonRosterScanRowFactory = Callable[..., Any]
SeasonRosterScanSummaryFactory = Callable[..., Any]
SimulationSummaryFactory = Callable[..., Any]
SkillSuccessBucketFactory = Callable[..., Any]
ValidateQualifyCutoffFn = Callable[[int, int], None]


class MonteCarloAccumulator:
    def __init__(
        self,
        runners: Sequence[int],
        qualify_cutoff: int = 4,
        *,
        validate_qualify_cutoff_fn: ValidateQualifyCutoffFn,
    ) -> None:
        self.runners = tuple(runners)
        self.index = {runner: i for i, runner in enumerate(self.runners)}
        size = len(self.runners)
        validate_qualify_cutoff_fn(qualify_cutoff, len(self.runners))
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

    def add(self, result: Any) -> None:
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

    def to_summary(
        self,
        config: Any,
        *,
        runner_name_lookup: RunnerNameLookup,
        runner_summary_factory: RunnerSummaryFactory,
        simulation_summary_factory: SimulationSummaryFactory,
        skill_success_bucket_factory: SkillSuccessBucketFactory,
    ) -> Any:
        rows: list[Any] = []
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
                skill_success_bucket_factory(
                    success_count=success_count,
                    races=bucket[0],
                    wins=bucket[1],
                    win_rate=bucket[1] / bucket[0] if bucket[0] else 0.0,
                )
                for success_count, bucket in sorted(self.skill_success_distribution[idx].items())
            )
            rows.append(
                runner_summary_factory(
                    runner=runner,
                    name=runner_name_lookup.get(runner, str(runner)),
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
        return simulation_summary_factory(iterations=n, config=config, rows=tuple(rows))


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

    def add_summary(self, summary: Any) -> None:
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
        elapsed_seconds: float | None,
        runner_name_lookup: RunnerNameLookup,
        row_factory: SeasonRosterScanRowFactory,
        summary_factory: SeasonRosterScanSummaryFactory,
    ) -> Any:
        rows: list[Any] = []
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
                row_factory(
                    runner=runner,
                    name=runner_name_lookup.get(runner, str(runner)),
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
        return summary_factory(
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
