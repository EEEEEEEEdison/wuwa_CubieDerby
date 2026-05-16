from __future__ import annotations

import json
import random
import time
from datetime import datetime
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Sequence

from cubie_derby_core.trace_logs import format_trace_metadata_lines


@dataclass(frozen=True)
class ChampionCLIHelpers:
    champion_prediction_to_dict: Callable[[Any], dict[str, object]]
    format_champion_prediction_summary: Callable[[Any], str]
    format_tournament_result: Callable[[Any], str]
    load_tournament_entry_request: Callable[[str | Path], Any]
    run_champion_prediction_from_entry_request_monte_carlo: Callable[..., Any]
    run_champion_prediction_monte_carlo: Callable[..., Any]
    simulate_tournament_from_entry_request: Callable[[Any, random.Random], Any]
    simulate_tournament: Callable[[int, random.Random], Any]
    tournament_result_to_dict: Callable[[Any], dict[str, object]]
    validate_champion_prediction_season: Callable[[int], None]


@dataclass(frozen=True)
class SeasonScanCLIHelpers:
    format_season_roster_scan_summary: Callable[[Any], str]
    run_season_roster_scan: Callable[..., Any]
    season_roster_scan_to_dict: Callable[[Any], dict[str, object]]


@dataclass(frozen=True)
class TraceCLIHelpers:
    format_simulation_overview_lines: Callable[..., list[str]]
    simulate_race: Callable[..., Any]
    trace_logger_factory: Callable[..., Any]
    trace_result_to_dict: Callable[[Any], dict[str, object]]


@dataclass(frozen=True)
class SimulationCLIHelpers:
    emit_progress_overview: Callable[[list[str]], None]
    format_simulation_overview_lines: Callable[..., list[str]]
    format_skill_ablation_summary: Callable[..., str]
    format_summary: Callable[..., str]
    parse_runner_tokens: Callable[[Sequence[str] | None], tuple[int, ...] | None]
    run_monte_carlo: Callable[..., Any]
    run_skill_ablation: Callable[..., Any]
    skill_ablation_to_dict: Callable[..., dict[str, object]]
    summary_to_dict: Callable[[Any], dict[str, object]]
    with_elapsed: Callable[[Any, float], Any]


def run_champion_prediction_command(
    args: Any,
    *,
    show_progress: bool,
    helpers: ChampionCLIHelpers,
) -> int:
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
    if args.tournament_context_out:
        raise ValueError("--tournament-context-out is only supported with --interactive")
    request = None
    season = args.season
    if args.tournament_context_in:
        request = helpers.load_tournament_entry_request(args.tournament_context_in)
        season = request.season
    helpers.validate_champion_prediction_season(season)
    if args.champion_prediction == "random":
        start_time = time.perf_counter()
        tournament = replace(
            (
                helpers.simulate_tournament_from_entry_request(request, random.Random(args.seed))
                if request is not None
                else helpers.simulate_tournament(season, random.Random(args.seed))
            ),
            elapsed_seconds=time.perf_counter() - start_time,
        )
        if args.json:
            print(json.dumps(helpers.tournament_result_to_dict(tournament), ensure_ascii=False, indent=2))
        else:
            print(helpers.format_tournament_result(tournament))
        return 0

    champion_summary = (
        helpers.run_champion_prediction_from_entry_request_monte_carlo(
            request,
            args.iterations,
            seed=args.seed,
            workers=args.workers,
            show_progress=show_progress,
        )
        if request is not None
        else helpers.run_champion_prediction_monte_carlo(
            season,
            args.iterations,
            seed=args.seed,
            workers=args.workers,
            show_progress=show_progress,
        )
    )
    if args.json:
        print(json.dumps(helpers.champion_prediction_to_dict(champion_summary), ensure_ascii=False, indent=2))
    else:
        print(helpers.format_champion_prediction_summary(champion_summary))
    return 0


def run_season_roster_scan_command(
    args: Any,
    *,
    show_progress: bool,
    helpers: SeasonScanCLIHelpers,
) -> int:
    if args.match_type:
        raise ValueError("--match-type cannot be combined with --season-roster-scan")
    summary = helpers.run_season_roster_scan(args, show_progress=show_progress)
    if args.json:
        print(json.dumps(helpers.season_roster_scan_to_dict(summary), ensure_ascii=False, indent=2))
    else:
        print(helpers.format_season_roster_scan_summary(summary))
    return 0


def run_trace_command(
    args: Any,
    config: Any,
    *,
    helpers: TraceCLIHelpers,
) -> int:
    generated_at = datetime.now()
    trace = helpers.trace_logger_factory(echo=args.trace)
    for line in format_trace_metadata_lines(
        config,
        seed=args.seed,
        generated_at=generated_at,
        format_simulation_overview_lines_fn=helpers.format_simulation_overview_lines,
    ):
        trace.write_line(line)
    result = helpers.simulate_race(config, random.Random(args.seed), trace=trace)
    result_text = json.dumps(helpers.trace_result_to_dict(result), ensure_ascii=False, indent=2)
    trace.write_line("")
    trace.write_line("=== 结果 ===")
    trace.write_line(result_text)
    if args.trace_log:
        path = Path(args.trace_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trace.text(), encoding="utf-8")
        print(f"过程日志已写入：{path}")
    return 0


def run_simulation_command(
    args: Any,
    config: Any,
    *,
    show_progress: bool,
    helpers: SimulationCLIHelpers,
) -> int:
    ablation_summary: Any | None = None
    if args.skill_ablation:
        targets = helpers.parse_runner_tokens(args.skill_ablation_runners)
        ablation_summary = helpers.run_skill_ablation(
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
            helpers.emit_progress_overview(
                helpers.format_simulation_overview_lines(
                    config,
                    args.iterations,
                    pending=True,
                )
            )
        summary = helpers.run_monte_carlo(
            config,
            args.iterations,
            seed=args.seed,
            workers=args.workers,
            show_progress=show_progress,
        )
        summary = helpers.with_elapsed(summary, time.perf_counter() - start_time)

    if args.json:
        data = helpers.summary_to_dict(summary)
        if ablation_summary is not None:
            data["skill_ablation"] = helpers.skill_ablation_to_dict(
                ablation_summary,
                include_detail=args.skill_ablation_detail,
            )
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        text = helpers.format_summary(summary)
        if ablation_summary is not None:
            text += "\n\n" + helpers.format_skill_ablation_summary(
                ablation_summary,
                detail=args.skill_ablation_detail,
            )
        print(text)
    return 0
