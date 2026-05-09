from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


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
}

NAME_TO_RUNNER: dict[str, int] = {name: runner for runner, name in RUNNER_NAMES.items()}


@dataclass(frozen=True)
class RaceConfig:
    runners: tuple[int, ...]
    track_length: int
    start_grid: tuple[tuple[int, ...], ...]
    random_start_stack: bool = False
    initial_order_mode: str = "random"  # random, start, fixed
    fixed_initial_order: tuple[int, ...] = ()
    name: str = "custom"


@dataclass(frozen=True)
class RaceResult:
    winner: int
    ranking: tuple[int, ...]
    second_position: int
    winner_margin: int


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
            track_length=22,
            start_grid=empty_grid(22),
            random_start_stack=True,
            initial_order_mode="random",
            name="mode1_random_order_random_start",
        )
    if mode == 2:
        selected = tuple(runners or (1, 2, 3, 4, 5, 6))
        return RaceConfig(
            runners=selected,
            track_length=22,
            start_grid=empty_grid(22),
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
            track_length=22,
            start_cells=start,
            initial_order=(9, 10, 7, 12, 8, 11),
        )
    if mode == 4:
        selected = tuple(runners or (3, 4, 8, 10))
        start = {1: (10,), 2: (4, 3), 3: (8,)}
        return fixed_grid_config(
            name="mode4_random_order_fixed_start",
            runners=selected,
            track_length=25,
            start_cells=start,
            initial_order=None,
        )
    if mode == 5:
        selected = tuple(runners or (7, 8, 9, 10, 11, 12))
        start = {1: (10, 7, 9), 2: (12,), 3: (8, 11)}
        return fixed_grid_config(
            name="mode5_fixed_order_fixed_start",
            runners=selected,
            track_length=25,
            start_cells=start,
            initial_order=(9, 8, 11, 7, 10, 12),
        )
    raise ValueError(f"unknown preset mode: {mode}")


def empty_grid(track_length: int) -> tuple[tuple[int, ...], ...]:
    return tuple(() for _ in range(track_length + 1))


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


def make_start_grid(track_length: int, cells: dict[int, Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    if track_length <= 0:
        raise ValueError("track_length must be positive")
    grid: list[tuple[int, ...]] = [() for _ in range(track_length + 1)]
    seen: set[int] = set()
    for pos, runners in cells.items():
        if pos < 0 or pos > track_length:
            raise ValueError(f"start position {pos} is outside the track")
        cell = tuple(runners)
        for runner in cell:
            if runner in seen:
                raise ValueError(f"runner {runner} appears more than once in start grid")
            seen.add(runner)
        grid[pos] = cell
    return tuple(grid)


def validate_fixed_start(runners: Sequence[int], grid: Sequence[Sequence[int]]) -> None:
    seen = tuple(runner for cell in grid for runner in cell)
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


def simulate_race(config: RaceConfig, rng: random.Random, trace: bool = False) -> RaceResult:
    runners = config.runners
    track_length = config.track_length
    grid = [list(cell) for cell in config.start_grid]

    if config.random_start_stack:
        start_stack = list(runners)
        rng.shuffle(start_stack)
        grid[0] = start_stack

    positions: dict[int, int] = {}
    for pos, cell in enumerate(grid):
        for runner in cell:
            positions[runner] = pos
    validate_positions(runners, positions)

    player_order = initial_player_order(config, grid, rng)
    cantarella_state = 1
    cantarella_group: list[int] = []
    zani_extra_steps = 0
    cartethyia_available = True
    cartethyia_extra_steps = False

    round_number = 1
    while True:
        log(trace, f"\n=== round {round_number} ===")
        log_grid(trace, grid)
        log(trace, "order: " + " -> ".join(map(str, player_order)))

        finished = False
        for player in list(player_order):
            if positions[player] >= track_length:
                continue

            current_pos = positions[player]
            current_cell = grid[current_pos]
            if player not in current_cell:
                raise RuntimeError(f"runner {player} is missing from position {current_pos}")
            idx_in_cell = current_cell.index(player)

            dice = roll_dice(player, rng)
            extra_steps = 0
            skip_carried_runners = False
            cantarella_move = False

            if player == 3:
                if current_rank(runners, positions, grid)[-1] == player:
                    extra_steps = 3
                    log(trace, "runner 3 skill: +3 because runner is last")
            elif player == 5:
                extra_steps = len(current_cell) - 1
                skip_carried_runners = True
                log(trace, f"runner 5 skill: +{extra_steps}, moves alone")
            elif player == 7:
                if player_order[-1] == player:
                    extra_steps = 2
                    log(trace, "runner 7 skill: +2 as last mover")
            elif player == 8:
                if player_order[0] == player:
                    extra_steps = 2
                    log(trace, "runner 8 skill: +2 as first mover")
            elif player == 9:
                cantarella_move = cantarella_state == 1
            elif player == 10:
                extra_steps = zani_extra_steps
                if len(current_cell) > 1 and rng.random() <= 0.4:
                    zani_extra_steps = 2
                    log(trace, "runner 10 skill: next action +2")
                else:
                    zani_extra_steps = 0
            elif player == 11:
                if cartethyia_extra_steps and rng.random() <= 0.6:
                    extra_steps = 2
                    log(trace, "runner 11 skill: +2")
            elif player == 12:
                if rng.random() <= 0.5:
                    extra_steps = 1
                    log(trace, "runner 12 skill: +1")

            total_steps = dice + extra_steps
            if player == 6 and rng.random() <= 0.28:
                total_steps += dice
                log(trace, f"runner 6 skill: repeats dice, total {total_steps}")

            log(trace, f"runner {player}: dice={dice}, total_steps={total_steps}")

            if cantarella_move:
                new_pos, cantarella_state, cantarella_group = move_cantarella(
                    grid=grid,
                    positions=positions,
                    player=player,
                    total_steps=total_steps,
                    track_length=track_length,
                    rng=rng,
                    cantarella_state=cantarella_state,
                    cantarella_group=cantarella_group,
                    trace=trace,
                )
            elif skip_carried_runners:
                new_pos = move_single_runner(
                    grid=grid,
                    positions=positions,
                    player=player,
                    total_steps=total_steps,
                    track_length=track_length,
                    rng=rng,
                )
            else:
                new_pos = move_runner_with_left_side(
                    grid=grid,
                    positions=positions,
                    player=player,
                    idx_in_cell=idx_in_cell,
                    total_steps=total_steps,
                    track_length=track_length,
                    rng=rng,
                )

            if player == 11 and cartethyia_available:
                if current_rank(runners, positions, grid)[-1] == player:
                    cartethyia_extra_steps = True
                    cartethyia_available = False

            log_grid(trace, grid)

            if new_pos >= track_length:
                finished = True
                break

        ranking = current_rank(runners, positions, grid)
        if finished:
            second_position = positions[ranking[1]] if len(ranking) > 1 else track_length
            return RaceResult(
                winner=ranking[0],
                ranking=tuple(ranking),
                second_position=second_position,
                winner_margin=track_length - second_position,
            )

        next_turn_last = check_player2_skill(grid, rng)
        if next_turn_last and 2 in runners:
            player_order = list(runners)
            rng.shuffle(player_order)
            player_order = [runner for runner in player_order if runner != 2] + [2]
        else:
            player_order = list(runners)
            rng.shuffle(player_order)

        if cantarella_state == 2:
            cantarella_state = 0

        round_number += 1


def validate_positions(runners: Sequence[int], positions: dict[int, int]) -> None:
    missing = set(runners) - set(positions)
    if missing:
        raise ValueError(f"missing start positions for: {format_runner_list(sorted(missing))}")


def initial_player_order(config: RaceConfig, grid: Sequence[Sequence[int]], rng: random.Random) -> list[int]:
    if config.initial_order_mode == "random":
        order = list(config.runners)
        rng.shuffle(order)
        return order
    if config.initial_order_mode == "start":
        order = [runner for cell in grid for runner in cell]
        validate_same_runners(config.runners, order, "initial start order")
        return order
    if config.initial_order_mode == "fixed":
        return list(config.fixed_initial_order)
    raise ValueError(f"unknown initial_order_mode: {config.initial_order_mode}")


def roll_dice(player: int, rng: random.Random) -> int:
    if player == 4:
        return rng.randint(2, 3)
    if player == 10:
        return 1 if rng.random() < 0.5 else 3
    return rng.randint(1, 3)


def move_single_runner(
    *,
    grid: list[list[int]],
    positions: dict[int, int],
    player: int,
    total_steps: int,
    track_length: int,
    rng: random.Random,
) -> int:
    current_pos = positions[player]
    old_cell = list(grid[current_pos])
    grid[current_pos] = [runner for runner in grid[current_pos] if runner != player]
    new_pos = min(current_pos + total_steps, track_length)
    positions[player] = new_pos
    add_group_to_position(grid, positions, [player], new_pos, old_cell, rng)
    return new_pos


def move_runner_with_left_side(
    *,
    grid: list[list[int]],
    positions: dict[int, int],
    player: int,
    idx_in_cell: int,
    total_steps: int,
    track_length: int,
    rng: random.Random,
) -> int:
    current_pos = positions[player]
    old_cell = list(grid[current_pos])
    left_runners = old_cell[:idx_in_cell]
    movers = left_runners + [player]
    grid[current_pos] = [runner for runner in old_cell if runner not in movers]
    new_pos = min(current_pos + total_steps, track_length)
    add_group_to_position(grid, positions, movers, new_pos, old_cell, rng)
    return new_pos


def move_cantarella(
    *,
    grid: list[list[int]],
    positions: dict[int, int],
    player: int,
    total_steps: int,
    track_length: int,
    rng: random.Random,
    cantarella_state: int,
    cantarella_group: list[int],
    trace: bool,
) -> tuple[int, int, list[int]]:
    new_pos = positions[player]
    group_mode = bool(cantarella_group)
    group = list(cantarella_group)

    for _ in range(total_steps):
        current_pos = positions[player]
        old_cell = list(grid[current_pos])
        if group_mode:
            movers = [runner for runner in group if positions[runner] == current_pos]
            if not movers:
                movers = [player]
        else:
            idx = old_cell.index(player)
            movers = old_cell[:idx] + [player]

        grid[current_pos] = [runner for runner in grid[current_pos] if runner not in movers]
        new_pos = min(current_pos + 1, track_length)
        add_group_to_position(grid, positions, movers, new_pos, old_cell, rng)
        log_grid(trace, grid)

        if not group_mode:
            old_set = set(old_cell)
            if any(runner not in old_set for runner in grid[new_pos]):
                group_mode = True
                group = list(grid[new_pos])
                cantarella_state = 2
                log(trace, "runner 9 skill: merged with destination group")

        if new_pos >= track_length:
            break

    return new_pos, cantarella_state, group


def add_group_to_position(
    grid: list[list[int]],
    positions: dict[int, int],
    movers: Sequence[int],
    new_pos: int,
    old_cell: Sequence[int],
    rng: random.Random,
) -> None:
    for runner in movers:
        positions[runner] = new_pos
    if grid[new_pos]:
        grid[new_pos] = list(movers) + grid[new_pos]
    else:
        grid[new_pos] = list(movers)
    grid[new_pos] = check_player1_skill(grid[new_pos], old_cell, rng)


def check_player1_skill(cell: list[int], old_cell: Sequence[int], rng: random.Random) -> list[int]:
    if cell == list(old_cell) or 1 not in cell or 1 in old_cell:
        return cell
    one_idx = cell.index(1)
    if one_idx > 0 and rng.random() <= 0.4:
        without_one = [runner for runner in cell if runner != 1]
        return [1] + without_one
    return cell


def check_player2_skill(grid: Sequence[Sequence[int]], rng: random.Random) -> bool:
    for cell in grid:
        if 2 in cell and cell.index(2) < len(cell) - 1:
            return rng.random() <= 0.65
    return False


def current_rank(runners: Sequence[int], positions: dict[int, int], grid: Sequence[Sequence[int]]) -> list[int]:
    cell_index: dict[int, int] = {}
    for cell in grid:
        for idx, runner in enumerate(cell):
            cell_index[runner] = idx
    return sorted(runners, key=lambda runner: (-positions[runner], cell_index.get(runner, 9999)))


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
        raise ValueError(f"runner id must be between 1 and 12: {runner}")
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
    cells: dict[int, tuple[int, ...]] = {}
    if not spec.strip():
        raise ValueError("start spec cannot be empty")
    for group in spec.split(";"):
        if not group.strip():
            continue
        if ":" not in group:
            raise ValueError(f"invalid start group {group!r}; expected 'position:runners'")
        pos_text, runners_text = group.split(":", 1)
        pos = int(pos_text.strip())
        runners = tuple(parse_runner(part) for part in runners_text.split(",") if part.strip())
        if not runners:
            raise ValueError(f"position {pos} has no runners")
        if pos in cells:
            raise ValueError(f"position {pos} is defined more than once")
        cells[pos] = runners
    all_runners = [runner for runners in cells.values() for runner in runners]
    if len(set(all_runners)) != len(all_runners):
        raise ValueError("start spec contains duplicate runners")
    return cells


def build_config_from_args(args: argparse.Namespace) -> RaceConfig:
    runners = parse_runner_tokens(args.runners)
    if args.start:
        base = preset_config(args.preset, runners)
        track_length = args.track_length or base.track_length
        start_cells = parse_start_spec(args.start)
        if runners is None:
            runners = tuple(runner for _, cell in sorted(start_cells.items()) for runner in cell)
        grid = make_start_grid(track_length, start_cells)
        validate_fixed_start(runners, grid)
        initial_order_mode = "random"
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
            random_start_stack=False,
            initial_order_mode=initial_order_mode,
            fixed_initial_order=fixed_order,
            name="custom",
        )

    config = preset_config(args.preset, runners)
    if args.track_length and args.track_length != config.track_length:
        max_pos = max((pos for pos, cell in enumerate(config.start_grid) if cell), default=0)
        if args.track_length < max_pos:
            raise ValueError("track length is shorter than a preset start position")
        cells = {pos: cell for pos, cell in enumerate(config.start_grid) if cell}
        config = RaceConfig(
            runners=config.runners,
            track_length=args.track_length,
            start_grid=make_start_grid(args.track_length, cells),
            random_start_stack=config.random_start_stack,
            initial_order_mode=config.initial_order_mode,
            fixed_initial_order=config.fixed_initial_order,
            name=config.name,
        )
    return config


def summary_to_dict(summary: SimulationSummary) -> dict[str, object]:
    return {
        "iterations": summary.iterations,
        "config": {
            "name": summary.config.name,
            "runners": list(summary.config.runners),
            "track_length": summary.config.track_length,
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
        f"Iterations: {summary.iterations:,}",
        f"Track length: {summary.config.track_length}",
        "",
        "runner        wins       win_rate   avg_rank   rank_var   gap/race   gap/when_win",
        "------------  ---------  ---------  ---------  ---------  ---------  ------------",
    ]
    for row in rows:
        label = f"{row.runner}.{row.name}"
        lines.append(
            f"{label:<12}  {row.wins:>9,}  {row.win_rate:>8.2%}  "
            f"{row.average_rank:>9.3f}  {row.rank_variance:>9.3f}  "
            f"{row.winner_gap_per_race:>9.3f}  {row.average_winning_margin:>12.3f}"
        )
    best = summary.best
    lines.extend(
        [
            "",
            f"Best pick: {best.runner}.{best.name} "
            f"with {best.win_rate:.2%} first-place probability.",
        ]
    )
    return "\n".join(lines)


def format_runner_list(runners: Iterable[int]) -> str:
    return ", ".join(f"{runner}.{RUNNER_NAMES.get(runner, str(runner))}" for runner in runners)


def log(enabled: bool, message: str) -> None:
    if enabled:
        print(message)


def log_grid(enabled: bool, grid: Sequence[Sequence[int]]) -> None:
    if not enabled:
        return
    for pos, cell in enumerate(grid):
        if cell:
            print(f"pos {pos}: {list(cell)}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulator for Wuthering Waves Cubie Derby.",
    )
    parser.add_argument("-n", "--iterations", type=int, default=100_000, help="number of races to simulate")
    parser.add_argument("--preset", type=int, choices=[1, 2, 3, 4, 5], default=4, help="built-in track preset")
    parser.add_argument("--runners", nargs="+", help="runner ids/names, e.g. --runners 3 4 8 10")
    parser.add_argument("--track-length", type=int, help="override track length")
    parser.add_argument(
        "--start",
        help="custom zero-based start grid, e.g. '1:10;2:4,3;3:8'. Overrides preset start grid.",
    )
    parser.add_argument(
        "--initial-order",
        help="custom first-round order: 'random', 'start', or comma-separated runner ids",
    )
    parser.add_argument("--seed", type=int, help="random seed for reproducible output")
    parser.add_argument("--workers", type=int, default=1, help="parallel workers; use 0 for CPU count")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--trace", action="store_true", help="print one traced race and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        config = build_config_from_args(args)
        if args.trace:
            result = simulate_race(config, random.Random(args.seed), trace=True)
            print(
                json.dumps(
                    {
                        "winner": result.winner,
                        "ranking": list(result.ranking),
                        "second_position": result.second_position,
                        "winner_margin": result.winner_margin,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
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


if __name__ == "__main__":
    raise SystemExit(main())
