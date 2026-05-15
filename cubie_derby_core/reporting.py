from __future__ import annotations

from typing import Any, Callable, Sequence


DisplayWidthFn = Callable[[str], int]
FormatOverviewFn = Callable[..., list[str]]
FormatRunnerFn = Callable[[int], str]
FormatStartOverviewFn = Callable[[Any], str]
FormatTableFn = Callable[[Sequence[str], Sequence[int], Sequence[str]], str]
RateFn = Callable[[Any], float | None]


def summary_to_dict(
    summary: Any,
    *,
    races_per_second_fn: RateFn,
    format_start_overview_fn: FormatStartOverviewFn,
) -> dict[str, object]:
    config_data: dict[str, object] = {
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
        "start_grid": {str(pos): list(cell) for pos, cell in sorted(summary.config.start_grid.items()) if cell},
        "start_layout": format_start_overview_fn(summary.config),
        "disabled_skills": sorted(summary.config.disabled_skills),
        "show_qualify_stats": summary.config.show_qualify_stats,
    }
    if summary.config.match_type is not None:
        config_data["match_type"] = summary.config.match_type
    if summary.config.show_qualify_stats:
        config_data["qualify_cutoff"] = summary.config.qualify_cutoff
    rows: list[dict[str, object]] = []
    for row in summary.rows:
        row_data: dict[str, object] = {
            "runner": row.runner,
            "name": row.name,
            "wins": row.wins,
            "win_rate": row.win_rate,
            "average_rank": row.average_rank,
            "rank_variance": row.rank_variance,
            "winner_gap_per_race": row.winner_gap_per_race,
            "average_winning_margin": row.average_winning_margin,
            "lazy_win_rate": row.lazy_win_rate,
            "winner_carried_steps": row.winner_carried_steps,
            "winner_total_steps": row.winner_total_steps,
            "skill_average_success_count": row.skill_average_success_count,
            "skill_marginal_win_rate": row.skill_marginal_win_rate,
        }
        if summary.config.show_qualify_stats:
            row_data["qualify_count"] = row.qualify_count
            row_data["qualify_rate"] = row.qualify_rate
        rows.append(row_data)
    return {
        "iterations": summary.iterations,
        "elapsed_seconds": summary.elapsed_seconds,
        "races_per_second": races_per_second_fn(summary),
        "config": config_data,
        "best": {
            "runner": summary.best.runner,
            "name": summary.best.name,
            "win_rate": summary.best.win_rate,
            "average_rank": summary.best.average_rank,
        },
        "rows": rows,
    }


def skill_ablation_to_dict(
    summary: Any,
    *,
    include_detail: bool = False,
) -> dict[str, object]:
    rows = []
    for row in sorted(summary.rows, key=lambda item: item.net_win_rate, reverse=True):
        row_data: dict[str, object] = {
            "runner": row.runner,
            "name": row.name,
            "enabled_win_rate": row.enabled_win_rate,
            "disabled_win_rate": row.disabled_win_rate,
            "net_win_rate": row.net_win_rate,
            "skill_average_success_count": row.skill_average_success_count,
            "skill_marginal_win_rate": row.skill_marginal_win_rate,
        }
        if include_detail:
            row_data["success_distribution"] = [
                {
                    "success_count": bucket.success_count,
                    "races": bucket.races,
                    "wins": bucket.wins,
                    "win_rate": bucket.win_rate,
                }
                for bucket in row.success_distribution
            ]
        rows.append(row_data)
    return {
        "iterations_per_scenario": summary.iterations,
        "scenario_count": len(summary.rows) + 1,
        "total_simulated_races": summary.total_simulated_races,
        "elapsed_seconds": summary.elapsed_seconds,
        "races_per_second": skill_ablation_races_per_second(summary),
        "rows": rows,
    }


def season_roster_scan_to_dict(summary: Any) -> dict[str, object]:
    return {
        "season": summary.season,
        "roster": list(summary.roster),
        "field_size": summary.field_size,
        "qualify_cutoff": summary.qualify_cutoff,
        "iterations_per_combination": summary.iterations_per_combination,
        "combination_count": summary.combination_count,
        "total_simulated_races": summary.total_simulated_races,
        "start": summary.start_spec,
        "track_length": summary.track_length,
        "initial_order_mode": summary.initial_order_mode,
        "elapsed_seconds": summary.elapsed_seconds,
        "races_per_second": season_roster_scan_races_per_second(summary),
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
                "combination_count": row.combination_count,
                "race_count": row.race_count,
                "wins": row.wins,
                "win_rate": row.win_rate,
                "qualify_count": row.qualify_count,
                "qualify_rate": row.qualify_rate,
                "average_rank": row.average_rank,
                "rank_variance": row.rank_variance,
                "winner_gap_per_race": row.winner_gap_per_race,
                "average_winning_margin": row.average_winning_margin,
                "lazy_win_rate": row.lazy_win_rate,
                "winner_carried_steps": row.winner_carried_steps,
                "winner_total_steps": row.winner_total_steps,
            }
            for row in summary.rows
        ],
    }


def format_summary(
    summary: Any,
    *,
    sort_by_win_rate: bool,
    format_runner_fn: FormatRunnerFn,
    display_width_fn: DisplayWidthFn,
    format_simulation_overview_lines_fn: FormatOverviewFn,
    format_table_row_fn: FormatTableFn,
    format_table_separator_fn: Callable[[Sequence[int]], str],
    races_per_second_fn: RateFn,
) -> str:
    rows = list(summary.rows)
    if sort_by_win_rate:
        rows.sort(key=lambda row: (row.win_rate, -row.average_rank), reverse=True)

    if summary.config.show_qualify_stats:
        headers = ("角色", "夺冠率", "晋级率", "平均名次", "名次方差", "场均领先", "胜时领先", "躺赢率")
        table_rows = [
            (
                format_runner_fn(row.runner),
                f"{row.win_rate:.2%}",
                f"{row.qualify_rate:.2%}",
                f"{row.average_rank:.3f}",
                f"{row.rank_variance:.3f}",
                f"{row.winner_gap_per_race:.3f}",
                f"{row.average_winning_margin:.3f}",
                f"{row.lazy_win_rate:.2%}",
            )
            for row in rows
        ]
        aligns = ("left", "right", "right", "right", "right", "right", "right", "right")
    else:
        headers = ("角色", "夺冠率", "平均名次", "名次方差", "场均领先", "胜时领先", "躺赢率")
        table_rows = [
            (
                format_runner_fn(row.runner),
                f"{row.win_rate:.2%}",
                f"{row.average_rank:.3f}",
                f"{row.rank_variance:.3f}",
                f"{row.winner_gap_per_race:.3f}",
                f"{row.average_winning_margin:.3f}",
                f"{row.lazy_win_rate:.2%}",
            )
            for row in rows
        ]
        aligns = ("left", "right", "right", "right", "right", "right", "right")
    columns = [headers, *table_rows]
    widths = [max(display_width_fn(row[idx]) for row in columns) for idx in range(len(headers))]

    lines = format_simulation_overview_lines_fn(
        summary.config,
        summary.iterations,
        elapsed_seconds=summary.elapsed_seconds,
        rate=races_per_second_fn(summary),
    )
    lines.extend(
        [
            "",
            format_table_row_fn(headers, widths, aligns),
            format_table_separator_fn(widths),
        ]
    )
    lines.extend(format_table_row_fn(row, widths, aligns) for row in table_rows)
    best = summary.best
    lines.extend(
        [
            "",
            f"推荐选择：{format_runner_fn(best.runner)}，夺冠概率 {best.win_rate:.2%}。",
        ]
    )
    return "\n".join(lines)


def format_season_roster_scan_summary(
    summary: Any,
    *,
    format_runner_fn: FormatRunnerFn,
    display_width_fn: DisplayWidthFn,
    format_season_roster_scan_overview_lines_fn: FormatOverviewFn,
    format_table_row_fn: FormatTableFn,
    format_table_separator_fn: Callable[[Sequence[int]], str],
) -> str:
    rows = sorted(summary.rows, key=lambda row: (row.win_rate, -row.average_rank), reverse=True)
    headers = ("角色", "参赛组合", "夺冠率", "晋级率", "平均名次", "名次方差", "场均领先", "胜时领先", "躺赢率")
    table_rows = [
        (
            format_runner_fn(row.runner),
            f"{row.combination_count:,}",
            f"{row.win_rate:.2%}",
            f"{row.qualify_rate:.2%}",
            f"{row.average_rank:.3f}",
            f"{row.rank_variance:.3f}",
            f"{row.winner_gap_per_race:.3f}",
            f"{row.average_winning_margin:.3f}",
            f"{row.lazy_win_rate:.2%}",
        )
        for row in rows
    ]
    columns = [headers, *table_rows]
    widths = [max(display_width_fn(row[idx]) for row in columns) for idx in range(len(headers))]
    aligns = ("left", "right", "right", "right", "right", "right", "right", "right", "right")
    lines = format_season_roster_scan_overview_lines_fn(
        season=summary.season,
        roster=summary.roster,
        field_size=summary.field_size,
        qualify_cutoff=summary.qualify_cutoff,
        start_spec=summary.start_spec,
        initial_order_mode=summary.initial_order_mode,
        combination_count=summary.combination_count,
        iterations_per_combination=summary.iterations_per_combination,
        total_simulated_races=summary.total_simulated_races,
        track_length=summary.track_length,
        elapsed_seconds=summary.elapsed_seconds,
        rate=season_roster_scan_races_per_second(summary),
    )
    lines.extend(
        [
            "",
            format_table_row_fn(headers, widths, aligns),
            format_table_separator_fn(widths),
        ]
    )
    lines.extend(format_table_row_fn(row, widths, aligns) for row in table_rows)
    best = summary.best
    lines.extend(
        [
            "",
            f"综合推荐：{format_runner_fn(best.runner)}，综合夺冠率 {best.win_rate:.2%}。",
        ]
    )
    return "\n".join(lines)


def format_skill_ablation_summary(
    summary: Any,
    *,
    detail: bool,
    format_runner_fn: FormatRunnerFn,
    display_width_fn: DisplayWidthFn,
    format_table_row_fn: FormatTableFn,
    format_table_separator_fn: Callable[[Sequence[int]], str],
    format_elapsed_fn: Callable[[float | None], str],
    format_rate_fn: Callable[[float | None], str],
) -> str:
    rows = sorted(summary.rows, key=lambda row: row.net_win_rate, reverse=True)
    headers = ("角色", "开启胜率", "关闭胜率", "净胜率", "平均成功次数", "单次边际胜率")
    table_rows = [
        (
            format_runner_fn(row.runner),
            f"{row.enabled_win_rate:.2%}",
            f"{row.disabled_win_rate:.2%}",
            f"{row.net_win_rate:+.2%}",
            f"{row.skill_average_success_count:.3f}",
            format_optional_signed_percent(row.skill_marginal_win_rate),
        )
        for row in rows
    ]
    columns = [headers, *table_rows]
    widths = [max(display_width_fn(row[idx]) for row in columns) for idx in range(len(headers))]
    aligns = ("left", "right", "right", "right", "right", "right")
    lines = [
        "技能消融统计：",
        f"每组模拟：{summary.iterations:,} 局",
        f"消融组数：{len(summary.rows)} 个角色 + 1 个技能全开基准",
        f"总模拟局数：{summary.total_simulated_races:,}",
        f"总用时：{format_elapsed_fn(summary.elapsed_seconds)}",
        f"总速度：{format_rate_fn(skill_ablation_races_per_second(summary))}",
        "",
        format_table_row_fn(headers, widths, aligns),
        format_table_separator_fn(widths),
    ]
    lines.extend(format_table_row_fn(row, widths, aligns) for row in table_rows)
    if detail:
        lines.extend(format_skill_ablation_detail(rows, format_runner_fn=format_runner_fn))
    return "\n".join(lines)


def format_skill_ablation_detail(rows: Sequence[Any], *, format_runner_fn: FormatRunnerFn) -> list[str]:
    lines = ["", "详细统计（技能全开基准局，按成功次数分布）："]
    for row in rows:
        lines.append(f"{format_runner_fn(row.runner)}：{format_success_distribution(row.success_distribution)}")
    return lines


def format_success_distribution(distribution: Sequence[Any]) -> str:
    grouped: dict[str, list[int]] = {
        "0次": [0, 0],
        "1次": [0, 0],
        "2次": [0, 0],
        "3次及以上": [0, 0],
    }
    for bucket in distribution:
        label = "3次及以上" if bucket.success_count >= 3 else f"{bucket.success_count}次"
        grouped[label][0] += bucket.races
        grouped[label][1] += bucket.wins
    parts = []
    for label, (races, wins) in grouped.items():
        if races:
            parts.append(f"{label} {races:,}局/{wins / races:.2%}")
    return "；".join(parts) if parts else "无数据"


def format_optional_signed_percent(value: float | None) -> str:
    if value is None:
        return "无数据"
    return f"{value:+.2%}"


def skill_ablation_races_per_second(summary: Any) -> float | None:
    if summary.elapsed_seconds is None or summary.elapsed_seconds <= 0:
        return None
    return summary.total_simulated_races / summary.elapsed_seconds


def season_roster_scan_races_per_second(summary: Any) -> float | None:
    if summary.elapsed_seconds is None or summary.elapsed_seconds <= 0:
        return None
    return summary.total_simulated_races / summary.elapsed_seconds
