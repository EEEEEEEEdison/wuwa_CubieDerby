from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class ChampionInteractiveHelpers:
    build_tournament_entry_request: Callable[..., Any]
    champion_prediction_to_dict: Callable[[Any], dict[str, object]]
    format_champion_prediction_summary: Callable[[Any], str]
    format_tournament_result: Callable[[Any], str]
    get_tournament_entry_point_definition: Callable[[int, str], Any]
    parse_runner_tokens: Callable[[Sequence[str] | None, random.Random | None, Sequence[int] | None], tuple[int, ...] | None]
    run_champion_prediction_from_entry_request_monte_carlo: Callable[..., Any]
    season_runner_pool: Callable[[int], Sequence[int]]
    simulate_tournament_from_entry_request: Callable[[Any, random.Random], Any]
    tournament_entry_point_choices: Callable[[int], Sequence[str]]
    tournament_entry_requirements: Callable[[int, str], Sequence[Any]]
    tournament_result_to_dict: Callable[[Any], dict[str, object]]
    validate_champion_prediction_season: Callable[[int], None]


def _prompt_line(
    prompt: str,
    *,
    default: str | None = None,
    input_fn: Callable[[str], str],
) -> str:
    prompt_text = f"{prompt}"
    if default is not None:
        prompt_text += f" [{default}]"
    prompt_text += "："
    while True:
        value = input_fn(prompt_text).strip()
        if value:
            return value
        if default is not None:
            return default


def _prompt_yes_no(
    prompt: str,
    *,
    default: bool,
    input_fn: Callable[[str], str],
) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        value = input_fn(f"{prompt} [{default_text}]：").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "是"}:
            return True
        if value in {"n", "no", "否"}:
            return False


def _prompt_choice(
    title: str,
    options: Sequence[tuple[str, str]],
    *,
    default_key: str | None = None,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> str:
    prompt_output_fn(title)
    for index, (_, label) in enumerate(options, start=1):
        prompt_output_fn(f"{index}. {label}")
    default_display = None
    if default_key is not None:
        for index, (key, _) in enumerate(options, start=1):
            if key == default_key:
                default_display = str(index)
                break
    while True:
        raw = _prompt_line("请输入序号", default=default_display, input_fn=input_fn)
        if raw.isdigit():
            choice_index = int(raw) - 1
            if 0 <= choice_index < len(options):
                return options[choice_index][0]
        prompt_output_fn("输入无效，请重新输入上面的序号。")


def _parse_runner_input(
    text: str,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
) -> tuple[int, ...]:
    tokens = [part for part in text.replace(",", " ").split() if part]
    runners = helpers.parse_runner_tokens(
        tokens,
        None,
        tuple(helpers.season_runner_pool(season)),
    )
    if runners is None:
        raise ValueError("未输入任何角色")
    return runners


def _prompt_runner_list(
    prompt: str,
    *,
    description: str,
    helpers: ChampionInteractiveHelpers,
    season: int,
    expected_count: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> tuple[int, ...]:
    prompt_output_fn(description)
    while True:
        raw = input_fn(f"{prompt}：").strip()
        try:
            runners = _parse_runner_input(raw, helpers=helpers, season=season)
            if len(runners) != expected_count:
                raise ValueError(f"需要输入 {expected_count} 名角色，当前是 {len(runners)} 名")
            return runners
        except ValueError as exc:
            prompt_output_fn(str(exc))


def _prompt_grouped_runner_list(
    requirement: Any,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> tuple[tuple[int, ...], ...] | None:
    if requirement.optional:
        wants_manual = _prompt_yes_no(
            f"{requirement.label}是否手动输入",
            default=False,
            input_fn=input_fn,
        )
        if not wants_manual:
            return None
    prompt_output_fn(requirement.description)
    groups: list[tuple[int, ...]] = []
    for index in range(requirement.group_count):
        group_name = chr(ord("A") + index)
        groups.append(
            _prompt_runner_list(
                f"请输入{group_name}组 {requirement.group_size} 名角色",
                description=f"按空格或逗号分隔输入第 {index + 1} 组角色。",
                helpers=helpers,
                season=season,
                expected_count=requirement.group_size,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
        )
    return tuple(groups)


def _prompt_requirement_value(
    requirement: Any,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> tuple[int, ...] | tuple[tuple[int, ...], ...] | None:
    if requirement.kind == "grouped-entrants":
        return _prompt_grouped_runner_list(
            requirement,
            helpers=helpers,
            season=season,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
    return _prompt_runner_list(
        requirement.label,
        description=requirement.description,
        helpers=helpers,
        season=season,
        expected_count=requirement.runner_count,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )


def run_interactive_champion_prediction_command(
    args: Any,
    *,
    show_progress: bool,
    helpers: ChampionInteractiveHelpers,
    input_fn: Callable[[str], str] | None = None,
    prompt_output_fn: Callable[[str], None] | None = None,
    result_output_fn: Callable[[str], None] | None = None,
) -> int:
    if input_fn is None:
        input_fn = input
    if prompt_output_fn is None:
        prompt_output_fn = print
    if result_output_fn is None:
        result_output_fn = print
    if args.season_roster_scan:
        raise ValueError("--interactive cannot be combined with --season-roster-scan")
    if args.skill_ablation:
        raise ValueError("--interactive cannot be combined with --skill-ablation")
    if args.trace or args.trace_log:
        raise ValueError("--interactive champion prediction does not support trace output")
    if args.runners is not None:
        raise ValueError("--interactive champion prediction does not accept --runners")
    if args.start or args.initial_order:
        raise ValueError("--interactive champion prediction does not accept --start or --initial-order")
    if args.match_type:
        raise ValueError("--interactive champion prediction does not accept --match-type")

    season = args.season
    helpers.validate_champion_prediction_season(season)
    prediction_mode = args.champion_prediction or _prompt_choice(
        "请选择冠军预测模式",
        (("random", "单届赛事"), ("monte-carlo", "Monte Carlo 统计")),
        default_key="random",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    entry_options = [
        (key, helpers.get_tournament_entry_point_definition(season, key).label)
        for key in helpers.tournament_entry_point_choices(season)
    ]
    entry_point = _prompt_choice(
        "请选择从哪个阶段开始",
        entry_options,
        default_key="group-a-round-1",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    requirement_values: dict[str, tuple[int, ...] | tuple[tuple[int, ...], ...]] = {}
    for requirement in helpers.tournament_entry_requirements(season, entry_point):
        value = _prompt_requirement_value(
            requirement,
            helpers=helpers,
            season=season,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if value is not None:
            requirement_values[requirement.key] = value

    request = helpers.build_tournament_entry_request(
        season=season,
        entry_point=entry_point,
        inputs=requirement_values,
    )
    seed_text = _prompt_line(
        "请输入随机种子（留空表示不固定）",
        default="" if args.seed is None else str(args.seed),
        input_fn=input_fn,
    )
    seed = int(seed_text) if seed_text else None
    json_output = _prompt_yes_no(
        "是否输出 JSON 结果",
        default=bool(args.json),
        input_fn=input_fn,
    )

    if prediction_mode == "random":
        start_time = time.perf_counter()
        tournament = replace(
            helpers.simulate_tournament_from_entry_request(request, random.Random(seed)),
            elapsed_seconds=time.perf_counter() - start_time,
        )
        if json_output:
            result_output_fn(json.dumps(helpers.tournament_result_to_dict(tournament), ensure_ascii=False, indent=2))
        else:
            result_output_fn(helpers.format_tournament_result(tournament))
        return 0

    iterations = int(
        _prompt_line(
            "请输入 Monte Carlo 模拟次数",
            default=str(args.iterations),
            input_fn=input_fn,
        )
    )
    workers = int(
        _prompt_line(
            "请输入 workers 数量（0 表示 CPU 核心数）",
            default=str(args.workers),
            input_fn=input_fn,
        )
    )
    summary = helpers.run_champion_prediction_from_entry_request_monte_carlo(
        request,
        iterations,
        seed=seed,
        workers=workers,
        show_progress=show_progress,
    )
    if json_output:
        result_output_fn(json.dumps(helpers.champion_prediction_to_dict(summary), ensure_ascii=False, indent=2))
    else:
        result_output_fn(helpers.format_champion_prediction_summary(summary))
    return 0
