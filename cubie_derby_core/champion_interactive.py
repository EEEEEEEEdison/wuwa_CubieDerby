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


def _remaining_entry_labels(
    *,
    season: int,
    entry_point: str,
    helpers: ChampionInteractiveHelpers,
) -> tuple[str, ...]:
    keys = tuple(helpers.tournament_entry_point_choices(season))
    start_index = keys.index(entry_point)
    return tuple(
        helpers.get_tournament_entry_point_definition(season, key).label
        for key in keys[start_index:]
    )


def _emit_champion_entry_guidance(
    *,
    season: int,
    entry_point: str,
    helpers: ChampionInteractiveHelpers,
    prompt_output_fn: Callable[[str], None],
    loaded_from_context: bool = False,
) -> None:
    definition = helpers.get_tournament_entry_point_definition(season, entry_point)
    remaining_labels = _remaining_entry_labels(season=season, entry_point=entry_point, helpers=helpers)
    prompt_output_fn(f"当前起始阶段：{definition.label}")
    if len(remaining_labels) == 1:
        prompt_output_fn(f"后续将模拟：{remaining_labels[0]}")
    else:
        prompt_output_fn(f"后续将依次模拟：{' -> '.join(remaining_labels)}")
    if loaded_from_context:
        prompt_output_fn("本次会直接使用已保存的上下文继续预测。")
    else:
        prompt_output_fn("下面会只询问继续推演到总决赛所必需的信息。")


def _requirement_summary_line(requirement: Any) -> str:
    if requirement.kind == "qualified":
        return (
            f"- {requirement.label}：可直接输入 {requirement.runner_count} 名晋级角色，"
            "也可以输入上一阶段完整排名后自动截取。"
        )
    if requirement.kind == "ranking":
        return f"- {requirement.label}：请按上一阶段第 1 名到第 {requirement.runner_count} 名的顺序输入。"
    if requirement.kind == "grouped-entrants":
        if requirement.optional:
            return (
                f"- {requirement.label}：可选。"
                f"如果你已经确定分组，可输入 {requirement.group_count} 组、每组 {requirement.group_size} 名；"
                "否则系统会按 seed 随机分组。"
            )
        return (
            f"- {requirement.label}：请输入 {requirement.group_count} 组、每组 {requirement.group_size} 名角色。"
        )
    return f"- {requirement.label}：请输入 {requirement.runner_count} 名角色。"


def _emit_requirement_overview(
    *,
    season: int,
    entry_point: str,
    helpers: ChampionInteractiveHelpers,
    prompt_output_fn: Callable[[str], None],
) -> None:
    requirements = tuple(helpers.tournament_entry_requirements(season, entry_point))
    if not requirements:
        return
    prompt_output_fn("接下来会需要这些信息：")
    for requirement in requirements:
        prompt_output_fn(_requirement_summary_line(requirement))


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
        raise ValueError("未输入任何角色")
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
    if entry_point == "group-a-round-2":
        mode = _prompt_choice(
            "小组A第二轮的补录方式",
            (
                ("direct", "分别输入小组A第二轮顺序，以及小组B/C第一轮名单"),
                ("derive", "输入小组A第一轮完整排名 + 小组B/C第一轮名单（共12名）"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            group_a_ranking = _prompt_runner_list(
                "请输入小组A第一轮完整排名（6名）",
                description="系统会直接把这 6 名作为小组A第二轮的参赛顺序。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            remaining_groups = _prompt_runner_list(
                "请输入小组B和小组C第一轮名单（共12名）",
                description="请按“小组B的 6 名在前，小组C的 6 名在后”的顺序输入，系统会自动拆成两组继续模拟。",
                helpers=helpers,
                season=season,
                expected_count=12,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "group-a-round-2-entrants": group_a_ranking,
                "group-b-round-1-entrants": remaining_groups[:6],
                "group-c-round-1-entrants": remaining_groups[6:],
            }
    if entry_point == "group-b-round-1":
        mode = _prompt_choice(
            "小组B第一轮的补录方式",
            (
                ("direct", "分别输入小组A晋级名单，以及小组B/C第一轮名单"),
                ("derive", "输入小组A第二轮完整排名 + 小组B/C第一轮名单（共12名）"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            group_a_ranking = _prompt_runner_list(
                "请输入小组A第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组A晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            remaining_groups = _prompt_runner_list(
                "请输入小组B和小组C第一轮名单（共12名）",
                description="请按“小组B的 6 名在前，小组C的 6 名在后”的顺序输入，系统会自动拆成两组继续模拟。",
                helpers=helpers,
                season=season,
                expected_count=12,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "group-a-round-2-qualified": group_a_ranking[:4],
                "group-b-round-1-entrants": remaining_groups[:6],
                "group-c-round-1-entrants": remaining_groups[6:],
            }
    if entry_point == "group-b-round-2":
        mode = _prompt_choice(
            "小组B第二轮的补录方式",
            (
                ("direct", "分别输入小组A晋级名单、小组B第二轮顺序和小组C第一轮名单"),
                ("derive", "输入小组A第二轮完整排名 + 小组B第一轮完整排名 + 小组C第一轮名单"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            group_a_ranking = _prompt_runner_list(
                "请输入小组A第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组A晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_b_ranking = _prompt_runner_list(
                "请输入小组B第一轮完整排名（6名）",
                description="系统会直接把这 6 名作为小组B第二轮的参赛顺序。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_c_entrants = _prompt_runner_list(
                "请输入小组C第一轮参赛角色（6名）",
                description="这些角色会继续完整跑完小组C的两轮比赛。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "group-a-round-2-qualified": group_a_ranking[:4],
                "group-b-round-2-entrants": group_b_ranking,
                "group-c-round-1-entrants": group_c_entrants,
            }
    if entry_point == "group-c-round-1":
        mode = _prompt_choice(
            "小组C第一轮的补录方式",
            (
                ("direct", "分别输入小组A/B晋级名单和小组C第一轮名单"),
                ("derive", "输入小组A/B第二轮完整排名 + 小组C第一轮名单"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            group_a_ranking = _prompt_runner_list(
                "请输入小组A第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组A晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_b_ranking = _prompt_runner_list(
                "请输入小组B第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组B晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_c_entrants = _prompt_runner_list(
                "请输入小组C第一轮参赛角色（6名）",
                description="这些角色会继续完整跑完小组C的两轮比赛。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "group-a-round-2-qualified": group_a_ranking[:4],
                "group-b-round-2-qualified": group_b_ranking[:4],
                "group-c-round-1-entrants": group_c_entrants,
            }
    if entry_point == "group-c-round-2":
        mode = _prompt_choice(
            "小组C第二轮的补录方式",
            (
                ("direct", "分别输入小组A/B晋级名单和小组C第二轮顺序"),
                ("derive", "输入小组A/B第二轮完整排名 + 小组C第一轮完整排名"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            group_a_ranking = _prompt_runner_list(
                "请输入小组A第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组A晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_b_ranking = _prompt_runner_list(
                "请输入小组B第二轮完整排名（6名）",
                description="系统会自动取前 4 名作为小组B晋级名单。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            group_c_ranking = _prompt_runner_list(
                "请输入小组C第一轮完整排名（6名）",
                description="系统会直接把这 6 名作为小组C第二轮的参赛顺序。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "group-a-round-2-qualified": group_a_ranking[:4],
                "group-b-round-2-qualified": group_b_ranking[:4],
                "group-c-round-2-entrants": group_c_ranking,
            }
    if entry_point == "elimination-a":
        mode = _prompt_choice(
            "淘汰赛分组的补录方式",
            (
                ("direct", "直接输入淘汰赛 A/B 两组名单"),
                ("ordered-qualified", "输入 12 名晋级者，前 6 名视为淘汰赛 A，后 6 名视为 B"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "ordered-qualified":
            qualified = _prompt_runner_list(
                "请输入 12 名小组赛晋级角色",
                description="按“淘汰赛 A 的 6 人在前，淘汰赛 B 的 6 人在后”的顺序输入，系统会自动拆成两组。",
                helpers=helpers,
                season=season,
                expected_count=12,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "elimination-a-entrants": qualified[:6],
                "elimination-b-entrants": qualified[6:],
            }
    if entry_point == "elimination-b":
        mode = _prompt_choice(
            "淘汰赛B的补录方式",
            (
                ("direct", "直接输入淘汰赛 A 排名和淘汰赛 B 名单"),
                ("derive", "输入 12 名晋级者和淘汰赛 A 完整排名，自动反推淘汰赛 B 名单"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            qualified = _prompt_runner_list(
                "请输入 12 名小组赛晋级角色",
                description="输入本阶段的全部 12 名晋级者；系统会用淘汰赛 A 的完整排名反推淘汰赛 B 的 6 人名单。",
                helpers=helpers,
                season=season,
                expected_count=12,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            qualified_set = set(qualified)
            while True:
                elimination_a = _prompt_runner_list(
                    "请输入淘汰赛A完整排名（6名）",
                    description="系统会自动把不在这 6 名中的其余晋级者归入淘汰赛 B。",
                    helpers=helpers,
                    season=season,
                    expected_count=6,
                    input_fn=input_fn,
                    prompt_output_fn=prompt_output_fn,
                )
                if any(runner not in qualified_set for runner in elimination_a):
                    prompt_output_fn("淘汰赛A排名中包含不在这 12 名晋级者里的角色，请重新输入。")
                    continue
                elimination_b = tuple(runner for runner in qualified if runner not in elimination_a)
                if len(elimination_b) != 6:
                    prompt_output_fn("淘汰赛A完整排名需要刚好占用 12 名晋级者中的 6 名，请重新输入。")
                    continue
                return {
                    "elimination-a-ranking": elimination_a,
                    "elimination-b-entrants": elimination_b,
                }
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
    if entry_point == "winners-round-2":
        mode = _prompt_choice(
            "胜者组的补录方式",
            (
                ("direct", "直接输入胜者组名单和败者组第一轮晋级名单"),
                ("derive", "输入淘汰赛 A/B 和败者组第一轮完整排名，自动推导剩余上下文"),
            ),
            default_key="direct",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
        if mode == "derive":
            elimination_a = _prompt_runner_list(
                "请输入淘汰赛A完整排名（6名）",
                description="系统会自动取前 3 名进入胜者组，后 3 名视作已进入败者组第一轮。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            elimination_b = _prompt_runner_list(
                "请输入淘汰赛B完整排名（6名）",
                description="系统会自动取前 3 名进入胜者组，后 3 名视作已进入败者组第一轮。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            losers_round_one = _prompt_runner_list(
                "请输入败者组第一轮完整排名（6名）",
                description="系统会自动取前 3 名继续进入败者组第二轮。",
                helpers=helpers,
                season=season,
                expected_count=6,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )
            return {
                "winners-round-2-entrants": elimination_a[:3] + elimination_b[:3],
                "losers-round-1-qualified": losers_round_one[:3],
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
    description = "请输入 6 名登场角色，使用空格或逗号分隔。"
    if getattr(rule, "seeded_from_runner_order", False):
        description = "请按上一轮第 1 名到第 6 名的顺序输入 6 名角色，系统会按这个顺序自动生成起跑站位。"
    prompt_output_fn(description)
    while True:
        raw = input_fn("请输入角色：").strip()
        try:
            tokens, runners = _parse_simulation_runner_input(
                raw,
                helpers=helpers,
                season=season,
            )
            if len(runners) != 6:
                raise ValueError(f"需要输入 6 名角色，当前是 {len(runners)} 名")
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
        "请选择单场模拟阶段",
        match_options,
        default_key="elimination",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    prompt_output_fn(f"当前模拟阶段：{helpers.get_match_type_rule(season, match_type).label}")
    prompt_output_fn("下面会继续询问登场角色、起跑配置、模拟次数和输出格式。")
    runner_tokens = args.runners or _prompt_simulation_runner_tokens(
        season=season,
        match_type=match_type,
        helpers=helpers,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    prompt_output_fn("默认起跑配置会根据当前阶段自动适配；如果你想覆盖，下一步可以手动输入自定义起跑。")
    use_custom_start = _prompt_yes_no(
        "是否覆盖默认起跑配置",
        default=bool(args.start),
        input_fn=input_fn,
    )
    start_spec = args.start if use_custom_start and args.start else None
    if use_custom_start and start_spec is None:
        start_spec = _prompt_line(
            "请输入自定义起跑配置，例如 1:* 或 -3:10;-2:4,3;-1:8",
            input_fn=input_fn,
        )
    iterations = int(
        _prompt_line(
            "请输入 Monte Carlo 模拟次数",
            default=str(args.iterations),
            input_fn=input_fn,
        )
    )
    seed_text = _prompt_line(
        "请输入随机种子，留空表示不固定",
        default="" if args.seed is None else str(args.seed),
        input_fn=input_fn,
    )
    seed = int(seed_text) if seed_text else None
    workers = int(
        _prompt_line(
            "请输入 workers 数量，0 表示使用 CPU 核心数",
            default=str(args.workers),
            input_fn=input_fn,
        )
    )
    json_output = _prompt_yes_no(
        "是否输出 JSON 结果",
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
    analysis_branch = _prompt_choice(
        "请选择分析大类",
        (
            ("champion", "赛事冠军预测"),
            ("simulation", "单场胜率分析"),
        ),
        default_key="champion",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    if analysis_branch == "simulation":
        prompt_output_fn("你正在进入“单场胜率分析”；下一步会先选择具体比赛阶段。")
        return run_interactive_simulation_command(
            args,
            show_progress=show_progress,
            helpers=simulation_helpers,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
    prompt_output_fn("你正在进入“赛事冠军预测”；下一步会选择单届演示或 Monte Carlo 统计。")
    prediction_mode = _prompt_choice(
        "请选择冠军预测方式",
        (
            ("random", "单届演示（跑 1 届完整赛事）"),
            ("monte-carlo", "Monte Carlo 分析（重复统计夺冠率）"),
        ),
        default_key="random",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
    )
    return run_interactive_champion_prediction_command(
        _with_args(args, champion_prediction=prediction_mode),
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
        _emit_champion_entry_guidance(
            season=season,
            entry_point=request.entry_point,
            helpers=helpers,
            prompt_output_fn=prompt_output_fn,
            loaded_from_context=True,
        )
    else:
        season = args.season
        helpers.validate_champion_prediction_season(season)
    prediction_mode = args.champion_prediction or _prompt_choice(
        "请选择冠军预测方式",
        (
            ("random", "单届演示（跑 1 届完整赛事）"),
            ("monte-carlo", "Monte Carlo 分析（重复统计夺冠率）"),
        ),
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
        _emit_champion_entry_guidance(
            season=season,
            entry_point=entry_point,
            helpers=helpers,
            prompt_output_fn=prompt_output_fn,
        )
        _emit_requirement_overview(
            season=season,
            entry_point=entry_point,
            helpers=helpers,
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
