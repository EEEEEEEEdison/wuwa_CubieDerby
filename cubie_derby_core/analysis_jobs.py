from __future__ import annotations

import math
import random
import time
from dataclasses import replace
from itertools import combinations
from typing import Any, Callable, Sequence

BuildConfigFromArgsFn = Callable[..., Any]
EmitProgressOverviewFn = Callable[[list[str]], None]
FormatRunnerListFn = Callable[[Sequence[int]], str]
FormatSeasonRosterScanOverviewLinesFn = Callable[..., list[str]]
FormatSkillAblationOverviewLinesFn = Callable[..., list[str]]
ParseStartLayoutFn = Callable[[str], tuple[dict[int, tuple[int, ...]], int | None]]
ProgressFactory = Callable[..., Any]
RunMonteCarloFn = Callable[..., Any]
SeasonRosterAccumulatorFactory = Callable[[Sequence[int]], Any]
SeasonRulesFn = Callable[[int], dict[str, object]]
SeasonRunnerPoolFn = Callable[[int], tuple[int, ...]]
ValidateStartPositionFn = Callable[[int, int], None]


def resolve_skill_ablation_runners(
    selected_runners: Sequence[int],
    requested_runners: Sequence[int] | None,
    *,
    skill_runners: set[int] | frozenset[int],
    format_runner_list_fn: FormatRunnerListFn,
) -> tuple[int, ...]:
    selected = set(selected_runners)
    if requested_runners is None:
        runners = tuple(runner for runner in selected_runners if runner in skill_runners)
    else:
        runners = tuple(requested_runners)
        if len(set(runners)) != len(runners):
            raise ValueError("skill ablation runners contain duplicates")
        missing = set(runners) - selected
        if missing:
            raise ValueError(f"skill ablation runners are not selected: {format_runner_list_fn(sorted(missing))}")
    without_skills = [runner for runner in runners if runner not in skill_runners]
    if without_skills:
        raise ValueError(f"runners do not have implemented skill ablation: {format_runner_list_fn(without_skills)}")
    if not runners:
        raise ValueError("no selected runners have implemented skills to ablate")
    return runners


def run_skill_ablation(
    config: Any,
    iterations: int,
    *,
    targets: Sequence[int] | None = None,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
    skill_runners: set[int] | frozenset[int],
    resolve_skill_ablation_runners_fn: Callable[..., tuple[int, ...]],
    emit_progress_overview_fn: EmitProgressOverviewFn,
    format_skill_ablation_overview_lines_fn: FormatSkillAblationOverviewLinesFn,
    progress_factory: ProgressFactory,
    run_monte_carlo_fn: RunMonteCarloFn,
    skill_ablation_row_factory: Callable[..., Any],
    skill_ablation_summary_factory: Callable[..., Any],
    with_elapsed_fn: Callable[[Any, float], Any],
) -> Any:
    evaluated = resolve_skill_ablation_runners_fn(
        config.runners,
        targets,
        skill_runners=skill_runners,
    )

    total_start = time.perf_counter()
    if show_progress:
        emit_progress_overview_fn(
            format_skill_ablation_overview_lines_fn(
                config,
                iterations=iterations,
                scenario_count=len(evaluated) + 1,
                total_simulated_races=iterations * (len(evaluated) + 1),
                pending=True,
            )
        )
    progress = (
        progress_factory(iterations * (len(evaluated) + 1), "技能消融", enabled=show_progress)
        if show_progress
        else None
    )
    base_start = time.perf_counter()
    try:
        base_summary = with_elapsed_fn(
            run_monte_carlo_fn(config, iterations, seed=seed, workers=workers, progress=progress),
            time.perf_counter() - base_start,
        )
        base_rows = {row.runner: row for row in base_summary.rows}

        seed_rng = random.Random(seed)
        rows: list[Any] = []
        for runner in evaluated:
            disabled_seed = seed_rng.randrange(1, 2**63) if seed is not None else None
            disabled_config = replace(
                config,
                disabled_skills=frozenset(set(config.disabled_skills) | {runner}),
            )
            disabled_summary = run_monte_carlo_fn(
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
                skill_ablation_row_factory(
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

        return skill_ablation_summary_factory(
            iterations=iterations,
            total_simulated_races=iterations * (len(evaluated) + 1),
            base_summary=base_summary,
            rows=tuple(rows),
            elapsed_seconds=time.perf_counter() - total_start,
        )
    finally:
        if progress is not None:
            progress.close()


def validate_season_roster_scan_args(
    args: Any,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    parse_start_layout_fn: ParseStartLayoutFn,
    season_rules_fn: SeasonRulesFn,
    validate_start_position_fn: ValidateStartPositionFn,
) -> tuple[int, ...]:
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

    roster = season_runner_pool_fn(args.season)
    if args.field_size < 1 or args.field_size > len(roster):
        raise ValueError(f"--field-size must be between 1 and {len(roster)} for season {args.season}")

    start_cells, random_start_position = parse_start_layout_fn(args.start)
    if random_start_position is None or start_cells:
        raise ValueError("--season-roster-scan currently requires a reusable '*' start such as '1:*' or '-1:*'")
    track_length = args.track_length or int(season_rules_fn(args.season)["track_length"])
    validate_start_position_fn(random_start_position, track_length)
    return roster


def season_roster_combination_count(season: int, field_size: int, *, season_runner_pool_fn: SeasonRunnerPoolFn) -> int:
    roster = season_runner_pool_fn(season)
    if field_size < 0 or field_size > len(roster):
        raise ValueError(f"field_size must be between 0 and {len(roster)} for season {season}")
    return math.comb(len(roster), field_size)


def run_season_roster_scan(
    args: Any,
    *,
    show_progress: bool = False,
    validate_season_roster_scan_args_fn: Callable[[Any], tuple[int, ...]],
    build_config_from_args_fn: BuildConfigFromArgsFn,
    accumulator_factory: SeasonRosterAccumulatorFactory,
    emit_progress_overview_fn: EmitProgressOverviewFn,
    format_season_roster_scan_overview_lines_fn: FormatSeasonRosterScanOverviewLinesFn,
    progress_factory: ProgressFactory,
    run_monte_carlo_fn: RunMonteCarloFn,
    task_runner_fn: Callable[[list[tuple[Any, int, int | None]], int, Any], Any],
) -> Any:
    roster = validate_season_roster_scan_args_fn(args)
    combo_list = list(combinations(roster, args.field_size))
    total_start = time.perf_counter()
    acc = accumulator_factory(roster)
    seed_rng = random.Random(args.seed)
    task_args = [
        (
            build_config_from_args_fn(args, runners_override=combo),
            args.iterations,
            seed_rng.randrange(1, 2**63) if args.seed is not None else None,
        )
        for combo in combo_list
    ]

    template_config = build_config_from_args_fn(args, runners_override=combo_list[0])
    if show_progress:
        emit_progress_overview_fn(
            format_season_roster_scan_overview_lines_fn(
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
    progress = progress_factory(len(combo_list) * args.iterations, "阵容遍历", enabled=show_progress) if show_progress else None

    try:
        task_runner_fn(task_args, args.workers, progress, acc, args.iterations, run_monte_carlo_fn)
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
