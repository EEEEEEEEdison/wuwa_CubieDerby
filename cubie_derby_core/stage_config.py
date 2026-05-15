from __future__ import annotations

import argparse
import random
from typing import Any, Callable, Sequence

from cubie_derby_core.match_types import MatchTypeRule

GetMatchTypeRuleFn = Callable[[int, str], MatchTypeRule]
MakeRaceConfigFn = Callable[..., Any]
BuildRaceConfigFn = Callable[..., Any]
ParseRunnerFn = Callable[[str], int]
ParseRunnerTokensFn = Callable[..., tuple[int, ...] | None]
ParseStartLayoutFn = Callable[[str], tuple[dict[int, tuple[int, ...]], int | None]]
ResolveMatchStartSpecFn = Callable[[MatchTypeRule, Sequence[int]], str]
EffectiveQualifyCutoffFn = Callable[[MatchTypeRule, int], int]
ResolveQualifyCutoffFn = Callable[[argparse.Namespace], int]
SeasonRulesFn = Callable[..., dict[str, object]]
SeasonRunnerPoolFn = Callable[[int], Sequence[int]]
ValidateQualifyCutoffFn = Callable[[int, int], None]
ValidateSameRunnersFn = Callable[[Sequence[int], Sequence[int], str], None]


def resolve_match_type_rule(
    *,
    season: int,
    match_type: str | None,
    get_match_type_rule_fn: GetMatchTypeRuleFn,
) -> MatchTypeRule | None:
    if not match_type:
        return None
    return get_match_type_rule_fn(season, match_type)


def default_initial_order_mode(grid: dict[int, Sequence[int]], random_start_position: int | None) -> str:
    nonempty_positions = [pos for pos, cell in grid.items() if cell]
    if random_start_position is not None:
        return "start"
    if nonempty_positions == [0]:
        return "start"
    return "random"


def parse_start_layout(
    spec: str,
    *,
    parse_runner_fn: ParseRunnerFn,
) -> tuple[dict[int, tuple[int, ...]], int | None]:
    cells: dict[int, tuple[int, ...]] = {}
    random_start_position: int | None = None
    if not spec.strip():
        raise ValueError("start spec cannot be empty")
    for group in spec.split(";"):
        if not group.strip():
            continue
        if ":" not in group:
            raise ValueError(f"invalid start group {group!r}; expected 'position:runners'")
        pos_text, runners_text = group.split(":", 1)
        pos = int(pos_text.strip())
        if runners_text.strip() == "*":
            if random_start_position is not None:
                raise ValueError("start spec can only contain one '*' random-stack group")
            random_start_position = pos
            continue
        runners = tuple(parse_runner_fn(part) for part in runners_text.split(",") if part.strip())
        if not runners:
            raise ValueError(f"position {pos} has no runners")
        if pos in cells:
            raise ValueError(f"position {pos} is defined more than once")
        cells[pos] = runners
    if random_start_position is not None and cells:
        raise ValueError("'*' means all selected runners start in that cell, so it cannot be mixed with fixed cells")
    all_runners = [runner for runners in cells.values() for runner in runners]
    if len(set(all_runners)) != len(all_runners):
        raise ValueError("start spec contains duplicate runners")
    return cells, random_start_position


def build_race_config(
    *,
    season: int,
    runners: Sequence[int],
    start_spec: str,
    track_length: int | None,
    initial_order: str | None,
    qualify_cutoff: int,
    race_config_factory: MakeRaceConfigFn,
    season_rules_fn: SeasonRulesFn,
    parse_start_layout_fn: ParseStartLayoutFn,
    validate_start_position_fn: Callable[[int, int], None],
    empty_grid_fn: Callable[[int], dict[int, tuple[int, ...]]],
    make_start_grid_fn: Callable[[int, dict[int, Sequence[int]]], dict[int, tuple[int, ...]]],
    validate_fixed_start_fn: Callable[[Sequence[int], dict[int, Sequence[int]]], None],
    validate_qualify_cutoff_fn: ValidateQualifyCutoffFn,
    parse_runner_tokens_fn: ParseRunnerTokensFn,
    validate_same_runners_fn: ValidateSameRunnersFn,
    match_rule: MatchTypeRule | None = None,
    name: str | None = None,
) -> Any:
    rules = season_rules_fn(season, match_rule=match_rule)
    selected_runners = tuple(runners)
    resolved_track_length = track_length or int(rules["track_length"])
    start_cells, random_start_position = parse_start_layout_fn(start_spec)
    if random_start_position is not None:
        validate_start_position_fn(random_start_position, resolved_track_length)
        if not selected_runners:
            raise ValueError("--runners is required when --start uses '*'")
        grid = empty_grid_fn(resolved_track_length)
    else:
        if not selected_runners:
            selected_runners = tuple(runner for _, cell in sorted(start_cells.items()) for runner in cell)
        grid = make_start_grid_fn(resolved_track_length, start_cells)
        validate_fixed_start_fn(selected_runners, grid)
    validate_qualify_cutoff_fn(qualify_cutoff, len(selected_runners))
    initial_order_mode = default_initial_order_mode(grid, random_start_position)
    fixed_order: tuple[int, ...] = ()
    if initial_order:
        if initial_order == "random":
            initial_order_mode = "random"
        elif initial_order == "start":
            initial_order_mode = "start"
        else:
            fixed_order = parse_runner_tokens_fn([initial_order]) or ()
            validate_same_runners_fn(selected_runners, fixed_order, "fixed initial order")
            initial_order_mode = "fixed"
    return race_config_factory(
        runners=selected_runners,
        track_length=resolved_track_length,
        start_grid=grid,
        qualify_cutoff=qualify_cutoff,
        season=season,
        forward_cells=rules["forward_cells"],
        backward_cells=rules["backward_cells"],
        shuffle_cells=rules["shuffle_cells"],
        npc_enabled=bool(rules["npc_enabled"]),
        random_start_stack=random_start_position is not None,
        random_start_position=random_start_position or 0,
        initial_order_mode=initial_order_mode,
        fixed_initial_order=fixed_order,
        match_type=match_rule.key if match_rule is not None else None,
        show_qualify_stats=match_rule.show_qualify_stats if match_rule is not None else True,
        name=name or (match_rule.label if match_rule is not None else "自定义"),
    )


def build_config_from_args(
    args: argparse.Namespace,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    parse_runner_tokens_fn: ParseRunnerTokensFn,
    resolve_match_type_rule_fn: Callable[[argparse.Namespace], MatchTypeRule | None],
    resolve_match_start_spec_fn: ResolveMatchStartSpecFn,
    effective_qualify_cutoff_fn: EffectiveQualifyCutoffFn,
    resolve_qualify_cutoff_fn: ResolveQualifyCutoffFn,
    build_race_config_fn: BuildRaceConfigFn,
    runners_override: Sequence[int] | None = None,
) -> Any:
    season = args.season
    runner_pool = season_runner_pool_fn(season)
    runners = (
        tuple(runners_override)
        if runners_override is not None
        else parse_runner_tokens_fn(args.runners, rng=random.Random(args.seed), runner_pool=runner_pool)
    )
    match_rule = resolve_match_type_rule_fn(args)
    if match_rule is None:
        if not args.start:
            raise ValueError("--start is required; pass a custom start grid such as '1:*' or '-3:2;-2:1,4;1:5'")
        start_spec = args.start
        qualify_cutoff = resolve_qualify_cutoff_fn(args)
    else:
        if runners is None:
            raise ValueError("--runners is required when --match-type is used")
        start_spec = args.start or resolve_match_start_spec_fn(match_rule, runners)
        qualify_cutoff = effective_qualify_cutoff_fn(match_rule, len(runners))
    return build_race_config_fn(
        season=season,
        runners=runners or (),
        start_spec=start_spec,
        track_length=args.track_length,
        initial_order=args.initial_order,
        qualify_cutoff=qualify_cutoff,
        match_rule=match_rule,
    )
