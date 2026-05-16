from __future__ import annotations

from typing import Any, Callable

AccumulatorFactory = Callable[..., Any]
ChunkFn = Callable[..., Any]
ChunkFromTupleFn = Callable[[tuple[Any, int, int | None, int]], Any]
CPUCounFn = Callable[[], int]
ParallelTaskCountFn = Callable[[int, int], int]
ProgressFactory = Callable[[int, str], Any]
SeasonRunnerPoolFn = Callable[[int], tuple[int, ...]]
SplitIterationsFn = Callable[[int, int], list[int]]
SummaryFactory = Callable[..., Any]
TournamentChunkFn = Callable[..., Any]
TournamentChunkFromTupleFn = Callable[[tuple[int, int, int | None, int, str]], Any]
TournamentEntryChunkFn = Callable[..., Any]
TournamentEntryChunkFromTupleFn = Callable[[tuple[Any, int, int | None, int, str]], Any]
PerfCounterFn = Callable[[], float]


def normalize_workers(iterations: int, workers: int, *, cpu_count_fn: CPUCounFn) -> int:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if workers == 0:
        workers = cpu_count_fn()
    return max(1, min(workers, iterations))


def run_monte_carlo(
    config: Any,
    iterations: int,
    *,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
    progress: Any | None = None,
    cpu_count_fn: CPUCounFn,
    progress_factory: ProgressFactory,
    parallel_task_count_fn: ParallelTaskCountFn,
    split_iterations_fn: SplitIterationsFn,
    simulate_chunk_fn: ChunkFn,
    simulate_chunk_from_tuple_fn: ChunkFromTupleFn,
    accumulator_factory: AccumulatorFactory,
    pool_factory: Callable[..., Any],
) -> Any:
    workers = normalize_workers(iterations, workers, cpu_count_fn=cpu_count_fn)

    owned_progress: Any | None = None
    if progress is None and show_progress:
        owned_progress = progress_factory(iterations, "模拟进度")
        progress = owned_progress

    try:
        if workers == 1:
            acc = simulate_chunk_fn(config, iterations, seed, progress=progress)
            return acc.to_summary(config)

        chunk_sizes = split_iterations_fn(iterations, parallel_task_count_fn(iterations, workers))
        chunk_args: list[tuple[Any, int, int | None, int]] = []
        start_index = 0
        for chunk_size in chunk_sizes:
            if chunk_size > 0:
                chunk_args.append((config, chunk_size, seed, start_index))
            start_index += chunk_size
        acc = accumulator_factory(config.runners, config.qualify_cutoff)
        with pool_factory(processes=workers) as pool:
            if progress is None:
                parts = pool.map(simulate_chunk_from_tuple_fn, chunk_args)
                for part in parts:
                    acc.merge(part)
            else:
                for part in pool.imap_unordered(simulate_chunk_from_tuple_fn, chunk_args):
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
    analysis_depth: str = "fast",
    cpu_count_fn: CPUCounFn,
    progress_factory: ProgressFactory,
    parallel_task_count_fn: ParallelTaskCountFn,
    split_iterations_fn: SplitIterationsFn,
    simulate_tournament_chunk_fn: TournamentChunkFn,
    simulate_tournament_chunk_from_tuple_fn: TournamentChunkFromTupleFn,
    accumulator_factory: AccumulatorFactory,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    pool_factory: Callable[..., Any],
    perf_counter_fn: PerfCounterFn,
    summary_factory: SummaryFactory,
) -> Any:
    workers = normalize_workers(iterations, workers, cpu_count_fn=cpu_count_fn)
    start_time = perf_counter_fn()

    owned_progress: Any | None = None
    progress: Any | None = None
    if show_progress:
        owned_progress = progress_factory(iterations, "冠军预测进度")
        progress = owned_progress

    try:
        if workers == 1:
            acc = simulate_tournament_chunk_fn(
                season,
                iterations,
                seed,
                progress=progress,
                analysis_depth=analysis_depth,
            )
        else:
            chunk_sizes = split_iterations_fn(iterations, parallel_task_count_fn(iterations, workers))
            chunk_args: list[tuple[int, int, int | None, int, str]] = []
            start_index = 0
            for chunk_size in chunk_sizes:
                if chunk_size > 0:
                    chunk_args.append((season, chunk_size, seed, start_index, analysis_depth))
                start_index += chunk_size
            acc = accumulator_factory(season_runner_pool_fn(season), analysis_depth)
            with pool_factory(processes=workers) as pool:
                if progress is None:
                    parts = pool.map(simulate_tournament_chunk_from_tuple_fn, chunk_args)
                    for part in parts:
                        acc.merge(part)
                else:
                    for part in pool.imap_unordered(simulate_tournament_chunk_from_tuple_fn, chunk_args):
                        acc.merge(part)
                        progress.advance(part.iterations)
        return summary_factory(acc, season=season, elapsed_seconds=perf_counter_fn() - start_time)
    finally:
        if owned_progress is not None:
            owned_progress.close()


def run_champion_prediction_from_entry_request_monte_carlo(
    request: Any,
    iterations: int,
    *,
    seed: int | None = None,
    workers: int = 1,
    show_progress: bool = False,
    analysis_depth: str = "fast",
    cpu_count_fn: CPUCounFn,
    progress_factory: ProgressFactory,
    parallel_task_count_fn: ParallelTaskCountFn,
    split_iterations_fn: SplitIterationsFn,
    simulate_tournament_from_entry_request_chunk_fn: TournamentEntryChunkFn,
    simulate_tournament_from_entry_request_chunk_from_tuple_fn: TournamentEntryChunkFromTupleFn,
    accumulator_factory: AccumulatorFactory,
    tournament_entry_request_roster_fn: Callable[[Any], tuple[int, ...]],
    pool_factory: Callable[..., Any],
    perf_counter_fn: PerfCounterFn,
    summary_factory: SummaryFactory,
) -> Any:
    workers = normalize_workers(iterations, workers, cpu_count_fn=cpu_count_fn)
    start_time = perf_counter_fn()

    owned_progress: Any | None = None
    progress: Any | None = None
    if show_progress:
        owned_progress = progress_factory(iterations, "冠军预测进度")
        progress = owned_progress

    try:
        if workers == 1:
            acc = simulate_tournament_from_entry_request_chunk_fn(
                request,
                iterations,
                seed,
                progress=progress,
                analysis_depth=analysis_depth,
            )
        else:
            chunk_sizes = split_iterations_fn(iterations, parallel_task_count_fn(iterations, workers))
            chunk_args: list[tuple[Any, int, int | None, int, str]] = []
            start_index = 0
            for chunk_size in chunk_sizes:
                if chunk_size > 0:
                    chunk_args.append((request, chunk_size, seed, start_index, analysis_depth))
                start_index += chunk_size
            acc = accumulator_factory(tournament_entry_request_roster_fn(request), analysis_depth)
            with pool_factory(processes=workers) as pool:
                if progress is None:
                    parts = pool.map(simulate_tournament_from_entry_request_chunk_from_tuple_fn, chunk_args)
                    for part in parts:
                        acc.merge(part)
                else:
                    for part in pool.imap_unordered(simulate_tournament_from_entry_request_chunk_from_tuple_fn, chunk_args):
                        acc.merge(part)
                        progress.advance(part.iterations)
        return summary_factory(acc, season=request.season, elapsed_seconds=perf_counter_fn() - start_time)
    finally:
        if owned_progress is not None:
            owned_progress.close()
