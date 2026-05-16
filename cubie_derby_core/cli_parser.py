from __future__ import annotations

import argparse
from typing import Callable, Sequence


MatchTypeChoicesFn = Callable[[], Sequence[str]]


def make_parser(*, match_type_choices_fn: MatchTypeChoicesFn) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulator for Wuthering Waves Cubie Derby.",
    )
    parser.add_argument("-n", "--iterations", type=int, default=100_000, help="number of races to simulate")
    parser.add_argument("--season", type=int, choices=[1, 2], default=1, help="season ruleset")
    parser.add_argument(
        "--match-type",
        help=(
            "season-aware stage rules, e.g. "
            + ", ".join(match_type_choices_fn())
            + "; Chinese aliases are also supported"
        ),
    )
    parser.add_argument(
        "--champion-prediction",
        choices=("random", "monte-carlo"),
        help="run a full season tournament instead of a single-stage simulation",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="launch interactive prompts for single-stage simulation or champion prediction",
    )
    parser.add_argument(
        "--tournament-context-in",
        help="load tournament entry context JSON for champion prediction; supports --interactive or direct --champion-prediction runs",
    )
    parser.add_argument(
        "--tournament-context-out",
        help="save resolved tournament entry context JSON during --interactive champion prediction",
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
    parser.add_argument(
        "--workers",
        "--worker",
        dest="workers",
        type=int,
        default=1,
        help="parallel workers; use 0 for CPU count",
    )
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
