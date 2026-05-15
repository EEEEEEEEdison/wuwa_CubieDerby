from __future__ import annotations

from typing import Callable, Sequence

FormatRunnerListFn = Callable[[Sequence[int]], str]
ValidateStartPositionFn = Callable[[int, int], None]


def validate_track_length(track_length: int) -> None:
    if track_length <= 0:
        raise ValueError("track_length must be positive")


def empty_grid(track_length: int) -> dict[int, tuple[int, ...]]:
    validate_track_length(track_length)
    return {}


def make_start_grid(
    track_length: int,
    cells: dict[int, Sequence[int]],
    *,
    validate_start_position_fn: ValidateStartPositionFn,
) -> dict[int, tuple[int, ...]]:
    validate_track_length(track_length)
    grid: dict[int, tuple[int, ...]] = {}
    seen: set[int] = set()
    for pos, runners in cells.items():
        validate_start_position_fn(pos, track_length)
        cell = tuple(runners)
        for runner in cell:
            if runner in seen:
                raise ValueError(f"runner {runner} appears more than once in start grid")
            seen.add(runner)
        if cell:
            grid[pos] = cell
    return grid


def validate_same_runners(
    expected: Sequence[int],
    actual: Sequence[int],
    label: str,
    *,
    format_runner_list_fn: FormatRunnerListFn,
) -> None:
    expected_set = set(expected)
    actual_set = set(actual)
    missing = expected_set - actual_set
    extra = actual_set - expected_set
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing runners: {format_runner_list_fn(sorted(missing))}")
        if extra:
            parts.append(f"extra runners: {format_runner_list_fn(sorted(extra))}")
        raise ValueError(f"{label} does not match selected runners ({'; '.join(parts)})")


def validate_fixed_start(
    runners: Sequence[int],
    grid: dict[int, Sequence[int]],
    *,
    validate_same_runners_fn: Callable[[Sequence[int], Sequence[int], str], None],
) -> None:
    seen = tuple(runner for _, cell in sorted(grid.items()) for runner in cell)
    validate_same_runners_fn(runners, seen, "start grid")


def validate_qualify_cutoff(qualify_cutoff: int, field_size: int) -> None:
    if qualify_cutoff < 1:
        raise ValueError("qualify cutoff must be at least 1")


def validate_positions(
    runners: Sequence[int],
    progress: dict[int, int],
    *,
    format_runner_list_fn: FormatRunnerListFn,
) -> None:
    missing = set(runners) - set(progress)
    if missing:
        raise ValueError(f"missing start positions for: {format_runner_list_fn(sorted(missing))}")
