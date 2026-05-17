"""Embedded smoke-test runner exposed via `python cubie_derby.py --smoke-test`.

Runs a small fixed-seed regression battery covering single-stage Monte
Carlo, champion prediction, and roster scan. Each scenario asserts that
the output matches an expected value captured at commit 8b29ffc on
2026-05-17 (the same baseline as tests/test_monte_carlo_pinned.py).

This is the CLI-facing twin of the pinned regression tests: CI runs both,
but contributors can also invoke it locally during big refactors as a
quick "did I drift the distribution?" check that prints a clear PASS/FAIL.
"""
from __future__ import annotations

import sys
import time
import types
from typing import Callable, TextIO


def _argparse_namespace(**overrides: object) -> object:
    defaults = {
        "season": 1,
        "match_type": None,
        "champion_prediction": None,
        "champion_analysis": "fast",
        "runners": None,
        "track_length": None,
        "start": None,
        "initial_order": None,
        "seed": None,
        "iterations": 100,
        "field_size": None,
        "workers": 1,
        "json": False,
        "trace": False,
        "trace_log": None,
        "season_roster_scan": False,
        "skill_ablation": False,
        "skill_ablation_runners": None,
        "skill_ablation_detail": False,
        "tournament_context_in": None,
        "tournament_context_out": None,
        "qualify_cutoff": 4,
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def run_smoke_tests(
    *,
    out: TextIO,
    build_config: Callable[..., object],
    run_monte_carlo: Callable[..., object],
    run_champion_prediction_monte_carlo: Callable[..., object],
    run_season_roster_scan: Callable[..., object],
    season2_lap_length: int,
    season2_group_forward_cells: frozenset[int],
    season2_group_backward_cells: frozenset[int],
    season2_group_shuffle_cells: frozenset[int],
) -> int:
    """Return 0 on success, 1 on any failure. Output is human-readable."""
    failures: list[str] = []

    def check(label: str, actual: object, expected: object) -> None:
        ok = actual == expected
        marker = "PASS" if ok else "FAIL"
        out.write(f"  [{marker}] {label}\n")
        if not ok:
            out.write(f"         expected: {expected!r}\n")
            out.write(f"         actual:   {actual!r}\n")
            failures.append(label)

    overall_start = time.perf_counter()

    # Scenario 1: single-stage Season 2 group, 2000 races, runners 11..16, seed=42.
    out.write(
        "Scenario 1: single-stage Season 2 group, 2,000 races, "
        "runners 11..16, seed=42\n"
    )
    runners = (11, 12, 13, 14, 15, 16)
    config = build_config(
        runners=runners,
        track_length=season2_lap_length,
        start_grid={1: runners},
        season=2,
        forward_cells=season2_group_forward_cells,
        backward_cells=season2_group_backward_cells,
        shuffle_cells=season2_group_shuffle_cells,
        npc_enabled=True,
        random_start_stack=True,
        random_start_position=1,
        initial_order_mode="random",
    )
    summary = run_monte_carlo(config, iterations=2000, seed=42, workers=1)
    rows = {row.runner: row for row in summary.rows}
    expected_wins = {11: 279, 12: 302, 13: 328, 14: 302, 15: 428, 16: 361}
    for runner_id, exp in expected_wins.items():
        check(f"  runner {runner_id} wins", rows[runner_id].wins, exp)
    check("  total wins", sum(row.wins for row in summary.rows), 2000)

    # Scenario 2: champion prediction, 300 tournaments, seed=42.
    out.write("Scenario 2: champion prediction Season 2 fast, 300 tournaments, seed=42\n")
    champ = run_champion_prediction_monte_carlo(
        season=2, iterations=300, seed=42, workers=1, analysis_depth="fast"
    )
    rows_by_id = {row.runner: row for row in champ.rows}
    expected_champs = {1: 16, 2: 14, 3: 16, 4: 18, 6: 17, 11: 12, 12: 24,
                       13: 4, 14: 7, 15: 21, 16: 11, 17: 35, 18: 9, 19: 37,
                       20: 36, 21: 7, 22: 4, 23: 12}
    for runner_id, exp in expected_champs.items():
        check(f"  runner {runner_id} championships",
              rows_by_id[runner_id].championships, exp)
    check("  total championships",
          sum(row.championships for row in champ.rows), 300)

    # Scenario 3: roster scan Season 1, field=2, 10 iters/combo, seed=42.
    out.write("Scenario 3: Season 1 roster scan field=2 iter=10 seed=42\n")
    args = _argparse_namespace(
        season=1, start="1:*", field_size=2, iterations=10, seed=42, workers=1,
    )
    scan = run_season_roster_scan(args)
    check("  combination count", scan.combination_count, 66)
    check("  total simulated races", scan.total_simulated_races, 660)
    expected_scan_wins = {1: 42, 2: 29, 3: 72, 4: 54, 5: 48, 6: 58,
                          7: 78, 8: 75, 9: 26, 10: 40, 11: 71, 12: 67}
    rows_by_id = {row.runner: row for row in scan.rows}
    for runner_id, exp in expected_scan_wins.items():
        check(f"  runner {runner_id} wins", rows_by_id[runner_id].wins, exp)

    elapsed = time.perf_counter() - overall_start
    out.write("\n")
    if failures:
        out.write(f"FAIL: {len(failures)} check(s) drifted ({elapsed:.2f}s)\n")
        return 1
    out.write(f"PASS: all checks reproduced expected values ({elapsed:.2f}s)\n")
    return 0
