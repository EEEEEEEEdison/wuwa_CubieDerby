from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class ChampionInteractiveHelpers:
    build_tournament_entry_request: Callable[..., Any]
    champion_prediction_to_dict: Callable[[Any], dict[str, object]]
    format_champion_prediction_summary: Callable[[Any], str]
    format_tournament_result: Callable[[Any], str]
    get_tournament_entry_point_definition: Callable[[int, str], Any]
    load_tournament_entry_request: Callable[[str | Path], Any]
    parse_runner_tokens: Callable[[Sequence[str] | None, random.Random | None, Sequence[int] | None], tuple[int, ...] | None]
    run_champion_prediction_from_entry_request_monte_carlo: Callable[..., Any]
    save_tournament_entry_request: Callable[[Any, str | Path], None]
    season_runner_pool: Callable[[int], Sequence[int]]
    simulate_tournament_from_entry_request: Callable[[Any, random.Random], Any]
    tournament_entry_point_choices: Callable[[int], Sequence[str]]
    tournament_entry_requirements: Callable[[int, str], Sequence[Any]]
    tournament_result_to_dict: Callable[[Any], dict[str, object]]
    validate_champion_prediction_season: Callable[[int], None]


@dataclass(frozen=True)
class SimulationInteractiveHelpers:
    build_config_from_args: Callable[[Any], Any]
    get_match_type_rule: Callable[[int, str], Any]
    match_type_choices: Callable[[], Sequence[str]]
    parse_runner_tokens: Callable[[Sequence[str] | None, random.Random | None, Sequence[int] | None], tuple[int, ...] | None]
    run_simulation_command: Callable[..., int]
    season_runner_pool: Callable[[int], Sequence[int]]
    simulation_cli_helpers: Any


def _with_args(args: Any, **updates: Any) -> Any:
    values = dict(vars(args))
    values.update(updates)
    return SimpleNamespace(**values)


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


def _parse_simulation_runner_input(
    text: str,
    *,
    helpers: SimulationInteractiveHelpers,
    season: int,
) -> tuple[list[str], tuple[int, ...]]:
    tokens = [part for part in text.replace(",", " ").split() if part]
    runners = helpers.parse_runner_tokens(
        tokens,
        None,
        tuple(helpers.season_runner_pool(season)),
    )
    if runners is None:
        raise ValueError("δ�����κν�ɫ")
    return tokens, runners


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


def _prompt_qualified_runner_list(
    requirement: Any,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> tuple[int, ...]:
    mode = _prompt_choice(
        f"{requirement.label}的提供方式",
        (
            ("direct", "直接输入晋级名单"),
            ("ranking", "输入上一阶段完整排名（6名）自动截取晋级名单"),
        ),
        default_key="direct",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    if mode == "ranking":
        ranking = _prompt_runner_list(
            f"请输入用于推导{requirement.label}的完整排名",
            description=f"{requirement.description}；如果你手头有上一阶段完整排名，可以直接输入 6 名角色，系统会自动取前 {requirement.runner_count} 名。",
            helpers=helpers,
            season=season,
            expected_count=6,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        return ranking[: requirement.runner_count]
    return _prompt_runner_list(
        requirement.label,
        description=requirement.description,
        helpers=helpers,
        season=season,
        expected_count=requirement.runner_count,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )


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
    if requirement.kind == "qualified":
        return _prompt_qualified_runner_list(
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


def _collect_derived_entry_inputs(
    *,
    season: int,
    entry_point: str,
    helpers: ChampionInteractiveHelpers,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> dict[str, tuple[int, ...] | tuple[tuple[int, ...], ...]]:
    if entry_point == "losers-round-1":
        mode = _prompt_choice(
            "败者组第一轮的补录方式",
            (
                ("direct", "直接输入败者组与胜者组当前名单"),
                ("derive", "输入淘汰赛 A/B 完整排名，自动推导胜者组和败者组名单"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            elimination_a = _prompt_runner_list(
                "请输入淘汰赛A完整排名（6名）",
                description="系统会自动取前 3 名并入胜者组，后 3 名并入败者组。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            elimination_b = _prompt_runner_list(
                "请输入淘汰赛B完整排名（6名）",
                description="系统会自动取前 3 名并入胜者组，后 3 名并入败者组。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "losers-round-1-entrants": elimination_a[3:] + elimination_b[3:],
                "winners-round-2-entrants": elimination_a[:3] + elimination_b[:3],
            }
    if entry_point == "losers-round-2":
        mode = _prompt_choice(
            "败者组第二轮的补录方式",
            (
                ("direct", "直接输入败者组第二轮名单和胜者组直通名单"),
                ("derive", "输入胜者组与败者组第一轮完整排名，自动推导剩余上下文"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            winners_round_two = _prompt_runner_list(
                "请输入胜者组完整排名（6名）",
                description="系统会自动取前 3 名直通总决赛，后 3 名进入败者组第二轮。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            losers_round_one = _prompt_runner_list(
                "请输入败者组第一轮完整排名（6名）",
                description="系统会自动取前 3 名进入败者组第二轮。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "winners-round-2-qualified": winners_round_two[:3],
                "losers-round-2-entrants": winners_round_two[3:] + losers_round_one[:3],
            }
    if entry_point == "grand-final":
        mode = _prompt_choice(
            "总决赛名单的提供方式",
            (
                ("direct", "直接输入总决赛 6 名角色"),
                ("derive", "输入胜者组与败者组第二轮完整排名，自动生成总决赛名单"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            winners_round_two = _prompt_runner_list(
                "请输入胜者组完整排名（6名）",
                description="系统会自动取前 3 名直通总决赛。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            losers_round_two = _prompt_runner_list(
                "请输入败者组第二轮完整排名（6名）",
                description="系统会自动取前 3 名补齐总决赛名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "grand-final-entrants": winners_round_two[:3] + losers_round_two[:3],
            }
    return {}


def _prompt_simulation_runner_tokens(
    *,
    season: int,
    match_type: str,
    helpers: SimulationInteractiveHelpers,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> list[str]:
    rule = helpers.get_match_type_rule(season, match_type)
    description = "������ 6 ����ɫ�����ո���ն��ŷָ���"
    if getattr(rule, "seeded_from_runner_order", False):
        description = "��С��ǰһ�ֵ������� 1 ���� 6 ��˳������ 6 ����ɫ��"
    prompt_output_fn(description)
    while True:
        raw = input_fn("��������ɫ��").strip()
        try:
            tokens, runners = _parse_simulation_runner_input(
                raw,
                helpers=helpers,
                season=season,
            )
            if len(runners) != 6:
                raise ValueError(f"��Ҫ���� 6 ����ɫ����ǰ�� {len(runners)} ��")
            return tokens
        except ValueError as exc:
            prompt_output_fn(str(exc))


def run_interactive_simulation_command(
    args: Any,
    *,
    show_progress: bool,
    helpers: SimulationInteractiveHelpers,
    input_fn: Callable[[str], str] | None = None,
    prompt_output_fn: Callable[[str], None] | None = None,
) -> int:
    if input_fn is None:
        input_fn = input
    if prompt_output_fn is None:
        prompt_output_fn = print
    if args.season_roster_scan:
        raise ValueError("--interactive cannot be combined with --season-roster-scan")
    if args.skill_ablation:
        raise ValueError("--interactive single-stage simulation does not support --skill-ablation yet")
    if args.trace or args.trace_log:
        raise ValueError("--interactive single-stage simulation does not support trace output yet")
    if args.tournament_context_in or args.tournament_context_out:
        raise ValueError("--tournament-context-in/out are only supported for interactive champion prediction")
    season = args.season
    if season != 2:
        raise ValueError("interactive single-stage simulation currently only supports --season 2")
    match_options = [
        (key, helpers.get_match_type_rule(season, key).label)
        for key in helpers.match_type_choices()
    ]
    match_type = args.match_type or _prompt_choice(
        "��ѡ�񵥳�ģ������",
        match_options,
        default_key="elimination",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    runner_tokens = args.runners or _prompt_simulation_runner_tokens(
        season=season,
        match_type=match_type,
        helpers=helpers,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    use_custom_start = _prompt_yes_no(
        "�Ƿ񸲸�Ĭ���𷽲���",
        default=bool(args.start),
        input_fn=input_fn,
    )
    start_spec = args.start if use_custom_start and args.start else None
    if use_custom_start and start_spec is None:
        start_spec = _prompt_line(
            "�������Զ����𷽣����� 1:* �� -3:10;-2:4,3;-1:8��",
            input_fn=input_fn,
        )
    iterations = int(
        _prompt_line(
            "������ Monte Carlo ģ�����",
            default=str(args.iterations),
            input_fn=input_fn,
        )
    )
    seed_text = _prompt_line(
        "������������ӣ����ձ�ʾ���̶���",
        default="" if args.seed is None else str(args.seed),
        input_fn=input_fn,
    )
    seed = int(seed_text) if seed_text else None
    workers = int(
        _prompt_line(
            "������ workers ������0 ��ʾ CPU ��������",
            default=str(args.workers),
            input_fn=input_fn,
        )
    )
    json_output = _prompt_yes_no(
        "�Ƿ���� JSON ���",
        default=bool(args.json),
        input_fn=input_fn,
    )
    interactive_args = _with_args(
        args,
        season=season,
        match_type=match_type,
        runners=runner_tokens,
        start=start_spec,
        initial_order=None,
        iterations=iterations,
        seed=seed,
        workers=workers,
        json=json_output,
        champion_prediction=None,
        trace=False,
        trace_log=None,
        skill_ablation=False,
        skill_ablation_runners=None,
        skill_ablation_detail=False,
        season_roster_scan=False,
    )
    config = helpers.build_config_from_args(interactive_args)
    return helpers.run_simulation_command(
        interactive_args,
        config,
        show_progress=show_progress,
        helpers=helpers.simulation_cli_helpers,
    )


def run_interactive_command(
    args: Any,
    *,
    show_progress: bool,
    champion_helpers: ChampionInteractiveHelpers,
    simulation_helpers: SimulationInteractiveHelpers,
    input_fn: Callable[[str], str] | None = None,
    prompt_output_fn: Callable[[str], None] | None = None,
    result_output_fn: Callable[[str], None] | None = None,
) -> int:
    if input_fn is None:
        input_fn = input
    if prompt_output_fn is None:
        prompt_output_fn = print
    if args.champion_prediction or args.tournament_context_in or args.tournament_context_out:
        return run_interactive_champion_prediction_command(
            args,
            show_progress=show_progress,
            helpers=champion_helpers,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            result_output_fn=result_output_fn,
        )
    if args.match_type or args.runners is not None or args.start or args.initial_order:
        return run_interactive_simulation_command(
            args,
            show_progress=show_progress,
            helpers=simulation_helpers,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
    mode = _prompt_choice(
        "��ѡ�񽻻���ģʽ",
        (
            ("champion-random", "��������Ԥ��"),
            ("champion-monte-carlo", "Monte Carlo �ھ�Ԥ��"),
            ("simulation", "����ģ��"),
        ),
        default_key="champion-random",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    if mode == "simulation":
        return run_interactive_simulation_command(
            args,
            show_progress=show_progress,
            helpers=simulation_helpers,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
    return run_interactive_champion_prediction_command(
        _with_args(args, champion_prediction="random" if mode == "champion-random" else "monte-carlo"),
        show_progress=show_progress,
        helpers=champion_helpers,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        result_output_fn=result_output_fn,
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

    request = None
    if args.tournament_context_in:
        request = helpers.load_tournament_entry_request(args.tournament_context_in)
        season = request.season
        helpers.validate_champion_prediction_season(season)
        prompt_output_fn(
            f"已从 {args.tournament_context_in} 载入赛事上下文："
            f"{helpers.get_tournament_entry_point_definition(season, request.entry_point).label}"
        )
    else:
        season = args.season
        helpers.validate_champion_prediction_season(season)
    prediction_mode = args.champion_prediction or _prompt_choice(
        "请选择冠军预测模式",
        (("random", "单届赛事"), ("monte-carlo", "Monte Carlo 统计")),
        default_key="random",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )

    if request is None:
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
        requirement_values = _collect_derived_entry_inputs(
            helpers=helpers,
            season=season,
            entry_point=entry_point,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        for requirement in helpers.tournament_entry_requirements(season, entry_point):
            if requirement.key in requirement_values:
                continue
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

    if args.tournament_context_out:
        helpers.save_tournament_entry_request(request, args.tournament_context_out)
        prompt_output_fn(f"赛事上下文已写入：{args.tournament_context_out}")

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
