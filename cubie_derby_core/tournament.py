from __future__ import annotations

import math
import random
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from cubie_derby_core.match_types import (
    MatchTypeRule,
    build_group_round_two_start_spec,
    effective_qualify_cutoff,
    eliminated_runners_for_rule,
    get_match_type_rule,
    qualified_runners_for_rule,
    resolve_match_start_spec,
)
from cubie_derby_core.runners import RUNNER_NAMES

BuildRaceConfigFn = Callable[..., Any]
DeriveSeedFn = Callable[[int, int], int]
ProgressBatchSizeFn = Callable[[int], int]
SeasonRunnerPoolFn = Callable[[int], Sequence[int]]
SimulateRaceFn = Callable[[Any, random.Random], Any]


@dataclass(frozen=True)
class StageResult:
    title: str
    match_type: str
    match_label: str
    entrants: tuple[int, ...]
    start_spec: str
    ranking: tuple[int, ...]
    qualified_runners: tuple[int, ...] = ()
    eliminated_runners: tuple[int, ...] = ()
    next_stage_start_spec: str | None = None
    show_qualify_stats: bool = True


@dataclass(frozen=True)
class TournamentResult:
    season: int
    stages: tuple[StageResult, ...]
    champion: int
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class ChampionPredictionRow:
    runner: int
    name: str
    championships: int
    champion_rate: float


@dataclass(frozen=True)
class ChampionPredictionSummary:
    season: int
    iterations: int
    rows: tuple[ChampionPredictionRow, ...]
    elapsed_seconds: float | None = None

    @property
    def best(self) -> ChampionPredictionRow:
        return max(self.rows, key=lambda row: row.champion_rate)


class ChampionPredictionAccumulator:
    def __init__(self, roster: Sequence[int]) -> None:
        self.roster = tuple(roster)
        self.index = {runner: i for i, runner in enumerate(self.roster)}
        self.iterations = 0
        self.championships = [0] * len(self.roster)

    def add(self, champion: int) -> None:
        self.iterations += 1
        self.championships[self.index[champion]] += 1

    def merge(self, other: "ChampionPredictionAccumulator") -> None:
        if self.roster != other.roster:
            raise ValueError("cannot merge champion accumulators for different rosters")
        self.iterations += other.iterations
        for index in range(len(self.roster)):
            self.championships[index] += other.championships[index]

    def to_summary(self, *, season: int, elapsed_seconds: float | None = None) -> ChampionPredictionSummary:
        rows = []
        total = self.iterations
        for runner in self.roster:
            championships = self.championships[self.index[runner]]
            rows.append(
                ChampionPredictionRow(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    championships=championships,
                    champion_rate=championships / total if total else math.nan,
                )
            )
        return ChampionPredictionSummary(
            season=season,
            iterations=total,
            rows=tuple(rows),
            elapsed_seconds=elapsed_seconds,
        )


def format_runner(runner: int) -> str:
    return RUNNER_NAMES.get(runner, "NPC" if runner < 0 else str(runner))


def format_runner_list(runners: Sequence[int]) -> str:
    return ", ".join(format_runner(runner) for runner in runners)


def format_runner_arrow_list(runners: Sequence[int]) -> str:
    return " -> ".join(format_runner(runner) for runner in runners)


def display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def pad_display_width(text: str, width: int, *, align: str = "left") -> str:
    padding = max(0, width - display_width(text))
    if align == "right":
        return " " * padding + text
    if align == "left":
        return text + " " * padding
    raise ValueError(f"unknown alignment: {align}")


def format_table_row(cells: Sequence[str], widths: Sequence[int], aligns: Sequence[str]) -> str:
    parts = [
        pad_display_width(cell, width, align=align)
        for cell, width, align in zip(cells, widths, aligns, strict=True)
    ]
    return "  ".join(parts)


def format_table_separator(widths: Sequence[int]) -> str:
    return "  ".join("-" * width for width in widths)


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


def split_random_groups(
    runners: Sequence[int],
    *,
    group_count: int,
    group_size: int,
    rng: random.Random,
) -> tuple[tuple[int, ...], ...]:
    total = group_count * group_size
    if len(runners) != total:
        raise ValueError(f"expected {total} runners, got {len(runners)}")
    shuffled = list(runners)
    rng.shuffle(shuffled)
    return tuple(
        tuple(shuffled[index : index + group_size])
        for index in range(0, total, group_size)
    )


def simulate_stage(
    *,
    season: int,
    match_type: str,
    runners: Sequence[int],
    rng: random.Random,
    build_race_config_fn: BuildRaceConfigFn,
    simulate_race_fn: SimulateRaceFn,
    start_spec: str | None = None,
    track_length: int | None = None,
    initial_order: str | None = None,
    title: str | None = None,
) -> StageResult:
    rule = get_match_type_rule(season, match_type)
    resolved_start_spec = start_spec or resolve_match_start_spec(rule, runners)
    config = build_race_config_fn(
        season=season,
        runners=runners,
        start_spec=resolved_start_spec,
        track_length=track_length,
        initial_order=initial_order,
        qualify_cutoff=effective_qualify_cutoff(rule, len(runners)),
        match_rule=rule,
        name=title or rule.label,
    )
    result = simulate_race_fn(config, rng)
    ranking = tuple(result.ranking)
    next_stage_start_spec = build_group_round_two_start_spec(ranking) if rule.emits_seed_layout else None
    return StageResult(
        title=title or rule.label,
        match_type=rule.key,
        match_label=rule.label,
        entrants=config.runners,
        start_spec=resolved_start_spec,
        ranking=ranking,
        qualified_runners=qualified_runners_for_rule(rule, ranking),
        eliminated_runners=eliminated_runners_for_rule(rule, ranking),
        next_stage_start_spec=next_stage_start_spec,
        show_qualify_stats=rule.show_qualify_stats,
    )


def validate_champion_prediction_season(season: int) -> None:
    if season != 2:
        raise ValueError("--champion-prediction currently only supports --season 2")


def simulate_tournament(
    season: int,
    rng: random.Random,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    simulate_stage_fn: Callable[..., StageResult],
) -> TournamentResult:
    validate_champion_prediction_season(season)
    roster = season_runner_pool_fn(season)
    stages: list[StageResult] = []
    group_stage_groups = split_random_groups(roster, group_count=3, group_size=6, rng=rng)
    group_round_two_qualifiers: list[int] = []
    for label, entrants in zip(("A", "B", "C"), group_stage_groups, strict=True):
        round_one = simulate_stage_fn(
            season=season,
            match_type="group-round-1",
            runners=entrants,
            rng=rng,
            title=f"小组赛第一轮 {label}组",
        )
        stages.append(round_one)
        round_two = simulate_stage_fn(
            season=season,
            match_type="group-round-2",
            runners=round_one.ranking,
            rng=rng,
            title=f"小组赛第二轮 {label}组",
        )
        stages.append(round_two)
        group_round_two_qualifiers.extend(round_two.qualified_runners)

    elimination_groups = split_random_groups(group_round_two_qualifiers, group_count=2, group_size=6, rng=rng)
    winners_round_two_entrants: list[int] = []
    losers_round_one_entrants: list[int] = []
    for label, entrants in zip(("A", "B"), elimination_groups, strict=True):
        elimination = simulate_stage_fn(
            season=season,
            match_type="elimination",
            runners=entrants,
            rng=rng,
            title=f"淘汰赛 {label}组",
        )
        stages.append(elimination)
        winners_round_two_entrants.extend(elimination.qualified_runners)
        losers_round_one_entrants.extend(elimination.eliminated_runners)

    losers_round_one = simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=tuple(losers_round_one_entrants),
        rng=rng,
        title="败者组第一轮",
    )
    stages.append(losers_round_one)

    winners_round_two = simulate_stage_fn(
        season=season,
        match_type="winners-bracket",
        runners=tuple(winners_round_two_entrants),
        rng=rng,
        title="胜者组第二轮",
    )
    stages.append(winners_round_two)

    losers_round_two = simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=tuple(winners_round_two.eliminated_runners + losers_round_one.qualified_runners),
        rng=rng,
        title="败者组第二轮",
    )
    stages.append(losers_round_two)

    grand_final = simulate_stage_fn(
        season=season,
        match_type="grand-final",
        runners=tuple(winners_round_two.qualified_runners + losers_round_two.qualified_runners),
        rng=rng,
        title="总决赛",
    )
    stages.append(grand_final)
    return TournamentResult(
        season=season,
        stages=tuple(stages),
        champion=grand_final.ranking[0],
    )


def simulate_tournament_chunk(
    season: int,
    iterations: int,
    seed: int | None,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    simulate_tournament_fn: Callable[[int, random.Random], TournamentResult],
    derive_seed_fn: DeriveSeedFn,
    progress_batch_size_fn: ProgressBatchSizeFn,
    start_index: int = 0,
    progress: Any | None = None,
) -> ChampionPredictionAccumulator:
    acc = ChampionPredictionAccumulator(season_runner_pool_fn(season))
    chunk_rng = random.Random(seed)
    progress_batch = progress_batch_size_fn(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            tournament_rng = chunk_rng
        else:
            tournament_rng = random.Random(derive_seed_fn(seed, start_index + index))
        acc.add(simulate_tournament_fn(season, tournament_rng).champion)
        pending_progress += 1
        if progress is not None and (pending_progress >= progress_batch or index == iterations - 1):
            progress.advance(pending_progress)
            pending_progress = 0
    return acc


def stage_result_to_dict(result: StageResult) -> dict[str, object]:
    data: dict[str, object] = {
        "title": result.title,
        "match_type": result.match_type,
        "match_label": result.match_label,
        "entrants": list(result.entrants),
        "start_spec": result.start_spec,
        "ranking": list(result.ranking),
    }
    if result.show_qualify_stats:
        data["qualified_runners"] = list(result.qualified_runners)
        data["eliminated_runners"] = list(result.eliminated_runners)
    if result.next_stage_start_spec is not None:
        data["next_stage_start_spec"] = result.next_stage_start_spec
    return data


def tournament_result_to_dict(result: TournamentResult) -> dict[str, object]:
    return {
        "season": result.season,
        "champion": result.champion,
        "champion_name": format_runner(result.champion),
        "elapsed_seconds": result.elapsed_seconds,
        "stages": [stage_result_to_dict(stage) for stage in result.stages],
    }


def champion_prediction_races_per_second(summary: ChampionPredictionSummary) -> float | None:
    if summary.elapsed_seconds is None or summary.elapsed_seconds <= 0:
        return None
    return summary.iterations / summary.elapsed_seconds


def champion_prediction_to_dict(summary: ChampionPredictionSummary) -> dict[str, object]:
    rows = sorted(summary.rows, key=lambda row: row.champion_rate, reverse=True)
    return {
        "season": summary.season,
        "iterations": summary.iterations,
        "elapsed_seconds": summary.elapsed_seconds,
        "tournaments_per_second": champion_prediction_races_per_second(summary),
        "best": {
            "runner": summary.best.runner,
            "name": summary.best.name,
            "championships": summary.best.championships,
            "champion_rate": summary.best.champion_rate,
        },
        "rows": [
            {
                "runner": row.runner,
                "name": row.name,
                "championships": row.championships,
                "champion_rate": row.champion_rate,
            }
            for row in rows
        ],
    }


def format_tournament_result(result: TournamentResult) -> str:
    lines = [
        "赛季冠军预测（单届）",
        format_runtime_status_line("赛季", f"第{result.season}季"),
        format_runtime_status_line("冠军", format_runner(result.champion)),
        format_runtime_status_line("用时", format_elapsed(result.elapsed_seconds)),
    ]
    for stage in result.stages:
        lines.extend(
            [
                "",
                stage.title,
                f"参赛：{format_runner_list(stage.entrants)}",
                f"起跑：{stage.start_spec}",
                f"排名：{format_runner_arrow_list(stage.ranking)}",
            ]
        )
        if stage.show_qualify_stats:
            lines.append(f"晋级：{format_runner_list(stage.qualified_runners)}")
            lines.append(f"淘汰：{format_runner_list(stage.eliminated_runners)}")
        if stage.next_stage_start_spec is not None:
            lines.append(f"下一轮站位：{stage.next_stage_start_spec}")
    return "\n".join(lines)


def format_champion_prediction_summary(summary: ChampionPredictionSummary) -> str:
    rows = sorted(summary.rows, key=lambda row: row.champion_rate, reverse=True)
    headers = ("角色", "夺冠率", "冠军次数")
    table_rows = [
        (
            row.name,
            f"{row.champion_rate:.2%}",
            f"{row.championships:,}",
        )
        for row in rows
    ]
    columns = [headers, *table_rows]
    widths = [max(display_width(row[idx]) for row in columns) for idx in range(len(headers))]
    aligns = ("left", "right", "right")
    lines = [
        "赛季冠军预测（统计）",
        format_runtime_status_line("赛季", f"第{summary.season}季"),
        format_runtime_status_line("模拟届数", f"{summary.iterations:,}"),
        format_runtime_status_line("用时", format_elapsed(summary.elapsed_seconds)),
        format_runtime_status_line("速度", format_rate(champion_prediction_races_per_second(summary))),
        "",
        format_table_row(headers, widths, aligns),
        format_table_separator(widths),
    ]
    lines.extend(format_table_row(row, widths, aligns) for row in table_rows)
    lines.extend(
        [
            "",
            f"推荐选择：{summary.best.name}，夺冠概率 {summary.best.champion_rate:.2%}。",
        ]
    )
    return "\n".join(lines)
