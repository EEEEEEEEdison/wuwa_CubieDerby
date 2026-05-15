from __future__ import annotations

from typing import Any, Callable, Sequence

from cubie_derby_core.match_types import MatchTypeRule

GetMatchTypeRuleFn = Callable[[int, str], MatchTypeRule]
MakeRaceConfigFn = Callable[..., Any]
ParseRunnerTokensFn = Callable[[Sequence[str] | None], tuple[int, ...] | None]
ParseStartLayoutFn = Callable[[str], tuple[dict[int, tuple[int, ...]], int | None]]
SeasonRulesFn = Callable[[int], dict[str, object]]
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
    rules = season_rules_fn(season)
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
