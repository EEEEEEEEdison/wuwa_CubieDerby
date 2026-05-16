from __future__ import annotations

import json
import random
import sys
import time
import unicodedata
from datetime import datetime
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence

from cubie_derby_core.interactive_i18n import translate_interactive_text
from cubie_derby_core.runners import RUNNER_ALIASES, RUNNER_NAMES
from cubie_derby_core.trace_logs import default_trace_log_path, format_trace_metadata_lines


PRIMARY_RUNNER_ALIASES: dict[int, str] = {}
for _alias, _runner in RUNNER_ALIASES.items():
    PRIMARY_RUNNER_ALIASES.setdefault(_runner, _alias)


@dataclass
class InteractiveWizardUI:
    prompt_output_fn: Callable[[str], None]
    lang: str
    compact_mode: bool = False
    summaries: list[tuple[str, str]] = field(default_factory=list)

    def set_summary(self, key: str, value: str) -> None:
        for index, (existing_key, _) in enumerate(self.summaries):
            if existing_key == key:
                self.summaries[index] = (key, value)
                return
        self.summaries.append((key, value))

    def start_block(self, title: str) -> None:
        if self.compact_mode:
            self.prompt_output_fn("\x1b[2J\x1b[H")
            if self.summaries:
                heading = "当前摘要" if self.lang == "zh" else "Current Summary"
                self.prompt_output_fn("-" * 24)
                self.prompt_output_fn(heading)
                self.prompt_output_fn("-" * 24)
                for _, line in self.summaries:
                    self.prompt_output_fn(f"  {line}")
                self.prompt_output_fn("")
        else:
            self.prompt_output_fn("")
        self.prompt_output_fn("=" * 24)
        self.prompt_output_fn(title)
        self.prompt_output_fn("=" * 24)


_ACTIVE_WIZARD_UI: InteractiveWizardUI | None = None


def _set_wizard_summary(key: str, value: str) -> None:
    if _ACTIVE_WIZARD_UI is not None:
        _ACTIVE_WIZARD_UI.set_summary(key, value)


class InteractiveTraceLogger:
    def __init__(self, echo_output_fn: Callable[[str], None] | None = None) -> None:
        self.echo_output_fn = echo_output_fn
        self.lines: list[str] = []

    def write_line(self, message: str) -> None:
        self.lines.append(message)
        if self.echo_output_fn is not None:
            self.echo_output_fn(message)

    def text(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")


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
    simulate_race: Callable[..., Any]
    simulation_cli_helpers: Any
    trace_result_to_dict: Callable[[Any], dict[str, object]]


def _with_args(args: Any, **updates: Any) -> Any:
    values = dict(vars(args))
    values.update(updates)
    return SimpleNamespace(**values)


def _prompt_line(
    prompt: str,
    *,
    input_fn: Callable[[str], str],
    translate_fn: Callable[[str], str] | None = None,
    allow_empty: bool = False,
) -> str:
    if translate_fn is None:
        translate_fn = lambda text: text
    prompt_text = translate_fn(prompt) + ": "
    while True:
        value = input_fn(prompt_text).strip()
        if value:
            return value
        if allow_empty:
            return ""


def _prompt_yes_no(
    prompt: str,
    *,
    input_fn: Callable[[str], str],
    translate_fn: Callable[[str], str] | None = None,
) -> bool:
    if translate_fn is None:
        translate_fn = lambda text: text
    english_mode = translate_fn("请输入序号") != "请输入序号"
    if english_mode:
        prompt_text = f"{translate_fn(prompt)} (yes/no): "
    else:
        prompt_text = f"{translate_fn(prompt)}（是/否）: "
    while True:
        value = input_fn(prompt_text).strip().lower()
        if value in {"y", "yes", "是"}:
            return True
        if value in {"n", "no", "否"}:
            return False


def _prompt_choice(
    title: str,
    options: Sequence[tuple[str, str]],
    *,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    translate_fn: Callable[[str], str] | None = None,
) -> str:
    if translate_fn is None:
        translate_fn = lambda text: text
    _emit_question_block(title=translate_fn(title), prompt_output_fn=prompt_output_fn)
    for index, (_, label) in enumerate(options, start=1):
        prompt_output_fn(f"{index}. {translate_fn(label)}")
    while True:
        raw = _prompt_line("请输入序号", input_fn=input_fn, translate_fn=translate_fn)
        if raw.isdigit():
            choice_index = int(raw) - 1
            if 0 <= choice_index < len(options):
                return options[choice_index][0]
        prompt_output_fn(translate_fn("输入无效，请重新输入上面的序号。"))


def _prompt_interactive_language(
    *,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
) -> str:
    prompt_output_fn("")
    prompt_output_fn("=" * 24)
    prompt_output_fn("Choose language / 请选择语言")
    prompt_output_fn("=" * 24)
    prompt_output_fn("1. 中文")
    prompt_output_fn("2. English")
    while True:
        raw = input_fn("Enter number / 请输入序号: ").strip()
        if raw == "1":
            return "zh"
        if raw == "2":
            return "en"
        prompt_output_fn("Invalid input. Please enter 1 or 2. / 输入无效，请输入 1 或 2。")


def _emit_question_block(
    *,
    title: str,
    prompt_output_fn: Callable[[str], None],
) -> None:
    if _ACTIVE_WIZARD_UI is not None:
        _ACTIVE_WIZARD_UI.start_block(title)
        return
    prompt_output_fn("")
    prompt_output_fn("=" * 24)
    prompt_output_fn(title)
    prompt_output_fn("=" * 24)


def _prompt_line_block(
    *,
    title: str,
    prompt: str,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    translate_fn: Callable[[str], str] | None = None,
    allow_empty: bool = False,
) -> str:
    _emit_question_block(title=title, prompt_output_fn=prompt_output_fn)
    return _prompt_line(
        prompt,
        input_fn=input_fn,
        translate_fn=translate_fn,
        allow_empty=allow_empty,
    )


def _prompt_yes_no_block(
    *,
    title: str,
    prompt: str,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    translate_fn: Callable[[str], str] | None = None,
) -> bool:
    _emit_question_block(title=title, prompt_output_fn=prompt_output_fn)
    return _prompt_yes_no(
        prompt,
        input_fn=input_fn,
        translate_fn=translate_fn,
    )


def _trace_mode_summary(mode: str, *, lang: str) -> str:
    if lang == "en":
        return {
            "none": "Trace = Off",
            "screen": "Trace = Screen",
            "file": "Trace = File",
            "both": "Trace = Screen + File",
        }[mode]
    return {
        "none": "过程日志 = 不输出",
        "screen": "过程日志 = 屏幕",
        "file": "过程日志 = 文件",
        "both": "过程日志 = 屏幕 + 文件",
    }[mode]


def _simulation_mode_summary(mode: str, *, lang: str) -> str:
    if lang == "en":
        return {
            "normal": "Run Mode = Monte Carlo",
            "debug": "Run Mode = Debug Trace",
        }[mode]
    return {
        "normal": "运行模式 = Monte Carlo",
        "debug": "运行模式 = 调试 Trace",
    }[mode]


def _champion_entry_mode_summary(mode: str, *, lang: str) -> str:
    if lang == "en":
        return {
            "from-start": "Entry = From beginning",
            "from-stage": "Entry = From specific stage",
        }[mode]
    return {
        "from-start": "入口 = 从头开始",
        "from-stage": "入口 = 从指定阶段开始",
    }[mode]


def _emit_interactive_trace_log(
    *,
    config: Any,
    seed: int | None,
    helpers: SimulationInteractiveHelpers,
    trace_mode: str,
    trace_log_path: str | None,
    prompt_output_fn: Callable[[str], None],
    lang: str,
) -> None:
    generated_at = datetime.now()
    screen_output_fn = prompt_output_fn if trace_mode in {"screen", "both"} else None
    trace = InteractiveTraceLogger(echo_output_fn=screen_output_fn)
    for line in format_trace_metadata_lines(
        config,
        seed=seed,
        generated_at=generated_at,
        format_simulation_overview_lines_fn=helpers.simulation_cli_helpers.format_simulation_overview_lines,
    ):
        trace.write_line(line)
    result = helpers.simulate_race(config, random.Random(seed), trace=trace)
    result_text = json.dumps(helpers.trace_result_to_dict(result), ensure_ascii=False, indent=2)
    trace.write_line("")
    trace.write_line("=== 结果 ===" if lang == "zh" else "=== Result ===")
    trace.write_line(result_text)
    if trace_mode in {"file", "both"} and trace_log_path:
        path = Path(trace_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trace.text(), encoding="utf-8")
        prompt_output_fn(
            f"过程日志已写入：{path}"
            if lang == "zh"
            else f"Trace log written to: {path}"
        )


def _runner_catalog_lines(
    *,
    season: int,
    runner_pool: Sequence[int],
    lang: str,
) -> list[str]:
    def display_width(text: str) -> int:
        width = 0
        for char in text:
            width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        return width

    def pad_display(text: str, target_width: int) -> str:
        return text + " " * max(0, target_width - display_width(text))

    entries = []
    for runner in runner_pool:
        if lang == "en":
            entries.append(f"{runner:>2} = {PRIMARY_RUNNER_ALIASES.get(runner, str(runner))}")
        else:
            entries.append(f"{runner:>2} = {RUNNER_NAMES.get(runner, str(runner))}")
    chunk_size = 3
    chunks = [entries[index : index + chunk_size] for index in range(0, len(entries), chunk_size)]
    column_width = max(display_width(entry) for entry in entries)
    if lang == "en":
        lines = [
            "You may enter runner IDs, Chinese names, or English aliases.",
            f"Available Season {season} runners:",
        ]
    else:
        lines = [
            "支持输入角色编号、中文名或英文别名。",
            f"本赛季可用角色：",
        ]
    lines.extend("  " + " | ".join(pad_display(entry, column_width) for entry in chunk) for chunk in chunks)
    return lines


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
    translate_fn: Callable[[str], str] | None = None,
    loaded_from_context: bool = False,
) -> None:
    if translate_fn is None:
        translate_fn = lambda text: text
    definition = helpers.get_tournament_entry_point_definition(season, entry_point)
    remaining_labels = _remaining_entry_labels(season=season, entry_point=entry_point, helpers=helpers)
    localized_definition_label = translate_fn(definition.label)
    localized_remaining_labels = tuple(translate_fn(label) for label in remaining_labels)
    prompt_output_fn(f"当前起始阶段：{localized_definition_label}")
    if len(remaining_labels) == 1:
        prompt_output_fn(f"后续将模拟：{localized_remaining_labels[0]}")
    else:
        prompt_output_fn(f"后续将依次模拟：{' -> '.join(localized_remaining_labels)}")
    if loaded_from_context:
        prompt_output_fn("本次会直接使用已保存的上下文继续预测。")
    else:
        prompt_output_fn("下面会只询问继续推演到总决赛所必需的信息。")


def _requirement_summary_line(
    requirement: Any,
    *,
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> str:
    if translate_fn is None:
        translate_fn = lambda text: text
    label = translate_fn(requirement.label)
    if lang == "en":
        if requirement.kind == "qualified":
            return (
                f"- {label}: enter {requirement.runner_count} qualifiers directly, "
                "or enter the full previous-stage ranking and let the wizard take the top finishers automatically."
            )
        if requirement.kind == "ranking":
            return f"- {label}: enter the previous-stage ranking from 1st through {requirement.runner_count}th."
        if requirement.kind == "grouped-entrants":
            if requirement.optional:
                return (
                    f"- {label}: optional. If the groups are already fixed, enter {requirement.group_count} groups "
                    f"with {requirement.group_size} runners each; otherwise the wizard will randomize them from the seed."
                )
            return f"- {label}: enter {requirement.group_count} groups with {requirement.group_size} runners each."
        return f"- {label}: enter {requirement.runner_count} runners."
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
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> None:
    if translate_fn is None:
        translate_fn = lambda text: text
    requirements = tuple(helpers.tournament_entry_requirements(season, entry_point))
    if not requirements:
        return
    prompt_output_fn("接下来会需要这些信息：")
    for requirement in requirements:
        prompt_output_fn(_requirement_summary_line(requirement, lang=lang, translate_fn=translate_fn))


def _parse_runner_input(
    text: str,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    lang: str = "zh",
) -> tuple[int, ...]:
    tokens = [part for part in text.replace(",", " ").split() if part]
    runners = helpers.parse_runner_tokens(
        tokens,
        None,
        tuple(helpers.season_runner_pool(season)),
    )
    if runners is None:
        raise ValueError("No runners were entered." if lang == "en" else "未输入任何角色")
    return runners


def _parse_simulation_runner_input(
    text: str,
    *,
    helpers: SimulationInteractiveHelpers,
    season: int,
    lang: str = "zh",
) -> tuple[list[str], tuple[int, ...]]:
    tokens = [part for part in text.replace(",", " ").split() if part]
    runners = helpers.parse_runner_tokens(
        tokens,
        None,
        tuple(helpers.season_runner_pool(season)),
    )
    if runners is None:
        raise ValueError("No runners were entered." if lang == "en" else "未输入任何角色")
    return tokens, runners


def _runner_display_name(runner: int, *, lang: str) -> str:
    if lang == "en":
        return PRIMARY_RUNNER_ALIASES.get(runner, str(runner))
    return RUNNER_NAMES.get(runner, str(runner))


def _merge_runner_batch(
    current: Sequence[int],
    incoming: Sequence[int],
    *,
    expected_count: int,
    lang: str,
) -> tuple[int, ...]:
    merged = list(current)
    seen = set(current)
    for runner in incoming:
        if runner in seen:
            display_name = _runner_display_name(runner, lang=lang)
            if lang == "en":
                raise ValueError(f"{display_name} was already entered.")
            raise ValueError(f"{display_name} 已经输入过了。")
        merged.append(runner)
        seen.add(runner)
    if len(merged) > expected_count:
        if lang == "en":
            raise ValueError(f"Too many runners. Need {expected_count}, but now have {len(merged)}.")
        raise ValueError(f"输入过多。需要 {expected_count} 名角色，当前累计 {len(merged)} 名")
    return tuple(merged)


def _emit_runner_progress(
    runners: Sequence[int],
    *,
    expected_count: int,
    prompt_output_fn: Callable[[str], None],
    lang: str,
) -> None:
    collapse_after = 3
    visible_tail = 3
    hidden_count = max(0, len(runners) - visible_tail)
    display_runners = runners if len(runners) <= collapse_after else runners[-visible_tail:]
    if lang == "en":
        if hidden_count > 0:
            prompt_output_fn(f"Recorded {len(runners)}/{expected_count} runners (collapsed first {hidden_count}):")
            prompt_output_fn(f"  ... {hidden_count} earlier runners hidden")
        else:
            prompt_output_fn(f"Recorded {len(runners)}/{expected_count} runners:")
        start_index = len(runners) - len(display_runners) + 1
        for index, runner in enumerate(display_runners, start=start_index):
            prompt_output_fn(f"  {index:>2}. {_runner_display_name(runner, lang=lang)}")
        prompt_output_fn(f"{expected_count - len(runners)} runners remaining.")
    else:
        if hidden_count > 0:
            prompt_output_fn(f"当前已记录 {len(runners)}/{expected_count} 名（已折叠前 {hidden_count} 名）：")
            prompt_output_fn(f"  ... 前 {hidden_count} 名已折叠")
        else:
            prompt_output_fn(f"当前已记录 {len(runners)}/{expected_count} 名：")
        start_index = len(runners) - len(display_runners) + 1
        for index, runner in enumerate(display_runners, start=start_index):
            prompt_output_fn(f"  {index:>2} = {_runner_display_name(runner, lang=lang)}")
        prompt_output_fn(f"还需要输入 {expected_count - len(runners)} 名角色。")


def _prompt_runner_list(
    prompt: str,
    *,
    title: str | None = None,
    description: str,
    helpers: ChampionInteractiveHelpers,
    season: int,
    expected_count: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
    show_catalog: bool = True,
) -> tuple[int, ...]:
    if translate_fn is None:
        translate_fn = lambda text: text
    if title is not None:
        _emit_question_block(title=title, prompt_output_fn=prompt_output_fn)
    if show_catalog:
        for line in _runner_catalog_lines(
            season=season,
            runner_pool=tuple(helpers.season_runner_pool(season)),
            lang=lang,
        ):
            prompt_output_fn(line)
    prompt_output_fn(description)
    current_runners: tuple[int, ...] = ()
    while True:
        raw = input_fn(f"{translate_fn(prompt)}: ").strip()
        try:
            runners = _parse_runner_input(raw, helpers=helpers, season=season, lang=lang)
            current_runners = _merge_runner_batch(
                current_runners,
                runners,
                expected_count=expected_count,
                lang=lang,
            )
            if len(current_runners) == expected_count:
                return current_runners
            _emit_runner_progress(
                current_runners,
                expected_count=expected_count,
                prompt_output_fn=prompt_output_fn,
                lang=lang,
            )
        except ValueError as exc:
            prompt_output_fn(str(exc))


def _prompt_qualified_runner_list(
    requirement: Any,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> tuple[int, ...]:
    if translate_fn is None:
        translate_fn = lambda text: text
    mode = _prompt_choice(
        f"{requirement.label}的提供方式",
        (
            ("direct", "直接输入晋级名单"),
            ("ranking", "输入上一阶段完整排名（6名）自动截取晋级名单"),
        ),
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        translate_fn=translate_fn,
    )
    if mode == "ranking":
        if lang == "en":
            description = (
                f"{translate_fn(requirement.description)} If you already have the full previous-stage ranking, "
                f"enter all 6 runners and the wizard will keep the top {requirement.runner_count} automatically."
            )
        else:
            description = (
                f"{requirement.description}；如果你手头有上一阶段完整排名，可以直接输入 6 名角色，"
                f"系统会自动取前 {requirement.runner_count} 名。"
            )
        ranking = _prompt_runner_list(
            f"请输入用于推导{requirement.label}的完整排名",
            title=f"{requirement.label}补录",
            description=description,
            helpers=helpers,
            season=season,
            expected_count=6,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
            translate_fn=translate_fn,
        )
        return ranking[: requirement.runner_count]
    return _prompt_runner_list(
        requirement.label,
        title=f"{requirement.label}补录",
        description=requirement.description,
        helpers=helpers,
        season=season,
        expected_count=requirement.runner_count,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        lang=lang,
        translate_fn=translate_fn,
    )


def _prompt_grouped_runner_list(
    requirement: Any,
    *,
    helpers: ChampionInteractiveHelpers,
    season: int,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> tuple[tuple[int, ...], ...] | None:
    if translate_fn is None:
        translate_fn = lambda text: text
    if requirement.optional:
        wants_manual = _prompt_yes_no(
            f"{requirement.label}是否手动输入",
            input_fn=input_fn,
            translate_fn=translate_fn,
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
                lang=lang,
                translate_fn=translate_fn,
                show_catalog=index == 0,
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
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> tuple[int, ...] | tuple[tuple[int, ...], ...] | None:
    if translate_fn is None:
        translate_fn = lambda text: text
    if requirement.kind == "grouped-entrants":
        return _prompt_grouped_runner_list(
            requirement,
            helpers=helpers,
            season=season,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
            translate_fn=translate_fn,
        )
    if requirement.kind == "qualified":
        return _prompt_qualified_runner_list(
            requirement,
            helpers=helpers,
            season=season,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
            translate_fn=translate_fn,
        )
    return _prompt_runner_list(
        requirement.label,
        description=requirement.description,
        helpers=helpers,
        season=season,
        expected_count=requirement.runner_count,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        lang=lang,
        translate_fn=translate_fn,
    )


def _collect_derived_entry_inputs(
    *,
    season: int,
    entry_point: str,
    helpers: ChampionInteractiveHelpers,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    lang: str = "zh",
    translate_fn: Callable[[str], str] | None = None,
) -> dict[str, tuple[int, ...] | tuple[tuple[int, ...], ...]]:
    del lang
    del translate_fn
    if entry_point == "group-a-round-2":
        mode = _prompt_choice(
            "小组A第二轮的补录方式",
            (
                ("direct", "分别输入小组A第二轮顺序，以及小组B/C第一轮名单"),
                ("derive", "输入小组A第一轮完整排名 + 小组B/C第一轮名单（共12名）"),
            ),
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
    match_type: str | None,
    helpers: SimulationInteractiveHelpers,
    input_fn: Callable[[str], str],
    prompt_output_fn: Callable[[str], None],
    lang: str = "zh",
    ) -> list[str]:
    rule = helpers.get_match_type_rule(season, match_type) if match_type is not None else None
    description = "请输入 6 名登场角色，使用空格或逗号分隔。"
    prompt_label = "请输入角色（可填编号、中文名或英文别名）"
    if rule is not None and getattr(rule, "seeded_from_runner_order", False):
        description = "请按上一轮第 1 名到第 6 名的顺序输入 6 名角色，系统会按这个顺序自动生成起跑站位。"
    if lang == "en":
        prompt_label = "Enter runners (IDs, Chinese names, or English aliases)"
    _emit_question_block(
        title="登场角色输入" if lang == "zh" else "Runner Entry",
        prompt_output_fn=prompt_output_fn,
    )
    for line in _runner_catalog_lines(
        season=season,
        runner_pool=tuple(helpers.season_runner_pool(season)),
        lang=lang,
    ):
        prompt_output_fn(line)
    prompt_output_fn(description)
    current_tokens: list[str] = []
    current_runners: tuple[int, ...] = ()
    while True:
        raw = input_fn(f"{prompt_label}: ").strip()
        try:
            tokens, runners = _parse_simulation_runner_input(
                raw,
                helpers=helpers,
                season=season,
                lang=lang,
            )
            current_runners = _merge_runner_batch(
                current_runners,
                runners,
                expected_count=6,
                lang=lang,
            )
            current_tokens.extend(tokens)
            if len(current_runners) == 6:
                return current_tokens
            _emit_runner_progress(
                current_runners,
                expected_count=6,
                prompt_output_fn=prompt_output_fn,
                lang=lang,
            )
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
    lang = getattr(args, "interactive_language", "zh")
    translate_fn = lambda text: translate_interactive_text(text, lang)
    raw_input_fn = input_fn
    raw_prompt_output_fn = prompt_output_fn
    input_fn = lambda prompt: raw_input_fn(translate_fn(prompt))
    prompt_output_fn = lambda text: raw_prompt_output_fn(translate_fn(text))
    if args.season_roster_scan:
        raise ValueError("--interactive cannot be combined with --season-roster-scan")
    if args.skill_ablation:
        raise ValueError("--interactive single-stage simulation does not support --skill-ablation yet")
    if args.tournament_context_in or args.tournament_context_out:
        raise ValueError("--tournament-context-in/out are only supported for interactive champion prediction")
    season = args.season
    season_label = f"第{season}季" if lang == "zh" else f"Season {season}"
    _set_wizard_summary("season", f"{'赛季' if lang == 'zh' else 'Season'} = {season_label}")
    _set_wizard_summary(
        "analysis",
        "分析 = 单场胜率分析" if lang == "zh" else "Analysis = Single-stage win-rate analysis",
    )
    if season == 2:
        match_options = [
            (key, helpers.get_match_type_rule(season, key).label)
            for key in helpers.match_type_choices()
        ]
        match_type = args.match_type or _prompt_choice(
            "请选择单场模拟阶段",
            match_options,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
        )
        localized_match_label = translate_fn(helpers.get_match_type_rule(season, match_type).label)
        _set_wizard_summary("stage", f"{'阶段' if lang == 'zh' else 'Stage'} = {localized_match_label}")
        prompt_output_fn(f"当前模拟阶段：{localized_match_label}")
        prompt_output_fn("下面会先选择普通分析还是调试模式，再继续询问登场角色和其他参数。")
    else:
        match_type = None
        _set_wizard_summary("stage", "阶段 = 基础单场分析" if lang == "zh" else "Stage = Basic single-stage analysis")
        prompt_output_fn("当前赛季暂不使用阶段化规则；下面会进行基础单场胜率分析。")
        prompt_output_fn("下面会先选择普通分析还是调试模式，再继续询问登场角色和其他参数。")
    if args.trace or args.trace_log:
        simulation_mode = "debug"
    else:
        simulation_mode = _prompt_choice(
            "请选择单场分析方式" if lang == "zh" else "Choose single-stage analysis mode",
            (
                ("normal", "普通分析（Monte Carlo 胜率）" if lang == "zh" else "Normal analysis (Monte Carlo win rates)"),
                ("debug", "调试模式（单局 Trace）" if lang == "zh" else "Debug mode (single traced race)"),
            ),
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
        )
    _set_wizard_summary("simulation_mode", _simulation_mode_summary(simulation_mode, lang=lang))
    runner_tokens = args.runners or _prompt_simulation_runner_tokens(
        season=season,
        match_type=match_type,
        helpers=helpers,
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        lang=lang,
    )
    _set_wizard_summary("runners", f"{'角色' if lang == 'zh' else 'Runners'} = 已选 {len(runner_tokens)} 名" if lang == "zh" else f"Runners = {len(runner_tokens)} selected")
    if season == 2:
        prompt_output_fn("默认起跑配置会根据当前阶段自动适配；如果你想覆盖，下一步可以手动输入自定义起跑。")
        if getattr(args, "_start_explicit", False):
            start_spec = args.start
            _set_wizard_summary("start", "起跑 = 自定义" if lang == "zh" else "Start = Custom")
        else:
            use_custom_start = _prompt_yes_no_block(
                title="起跑配置" if lang == "zh" else "Start Layout",
                prompt="是否覆盖默认起跑配置",
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
            start_spec = None
            if use_custom_start:
                start_spec = _prompt_line_block(
                    title="自定义起跑配置" if lang == "zh" else "Custom Start Layout",
                    prompt="请输入自定义起跑配置，例如 1:* 或 -3:10;-2:4,3;-1:8",
                    input_fn=input_fn,
                    prompt_output_fn=prompt_output_fn,
                    translate_fn=translate_fn,
                )
                _set_wizard_summary("start", "起跑 = 自定义" if lang == "zh" else "Start = Custom")
            else:
                _set_wizard_summary("start", "起跑 = 默认" if lang == "zh" else "Start = Default")
    else:
        if getattr(args, "_start_explicit", False):
            start_spec = args.start
            _set_wizard_summary("start", "起跑 = 自定义" if lang == "zh" else "Start = Custom")
        else:
            start_spec = _prompt_line_block(
                title="起跑配置" if lang == "zh" else "Start Layout",
                prompt="请输入起跑配置，例如 1:* 或 -3:2;-2:1,4;1:5",
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
            _set_wizard_summary("start", "起跑 = 自定义" if lang == "zh" else "Start = Custom")
    seed = args.seed
    if not getattr(args, "_seed_explicit", False):
        seed_text = _prompt_line_block(
            title="随机种子" if lang == "zh" else "Random Seed",
            prompt="请输入随机种子，留空表示不固定",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
            allow_empty=True,
        )
        seed = int(seed_text) if seed_text else None
    _set_wizard_summary("seed", f"{'种子' if lang == 'zh' else 'Seed'} = {seed if seed is not None else ('未固定' if lang == 'zh' else 'unfixed')}")
    json_output = args.json if getattr(args, "_json_explicit", False) else _prompt_yes_no_block(
        title="输出格式" if lang == "zh" else "Output Format",
        prompt="是否输出 JSON 结果",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        translate_fn=translate_fn,
    )
    _set_wizard_summary("output", "输出 = JSON" if (lang == "zh" and json_output) else ("输出 = 文本" if lang == "zh" else ("Output = JSON" if json_output else "Output = Text")))
    iterations = args.iterations
    workers = args.workers
    trace_mode = "none"
    trace_log_path = None
    if simulation_mode == "normal":
        if not getattr(args, "_iterations_explicit", False):
            iterations = int(
                _prompt_line_block(
                    title="模拟次数" if lang == "zh" else "Iterations",
                    prompt="请输入 Monte Carlo 模拟次数",
                    input_fn=input_fn,
                    prompt_output_fn=prompt_output_fn,
                    translate_fn=translate_fn,
                )
            )
        _set_wizard_summary("iterations", f"{'次数' if lang == 'zh' else 'Iterations'} = {iterations}")
        if not getattr(args, "_workers_explicit", False):
            workers = int(
                _prompt_line_block(
                    title="并行设置" if lang == "zh" else "Worker Count",
                    prompt="请输入 workers 数量，0 表示使用 CPU 核心数",
                    input_fn=input_fn,
                    prompt_output_fn=prompt_output_fn,
                    translate_fn=translate_fn,
                )
            )
        _set_wizard_summary("workers", f"{'并行' if lang == 'zh' else 'Workers'} = {workers}")
    else:
        iterations = 1
        workers = 1
        _set_wizard_summary("iterations", f"{'次数' if lang == 'zh' else 'Iterations'} = 1")
        _set_wizard_summary("workers", f"{'并行' if lang == 'zh' else 'Workers'} = 1")
        if args.trace and args.trace_log:
            trace_mode = "both"
            trace_log_path = args.trace_log
        elif args.trace:
            trace_mode = "screen"
            trace_log_path = None
        elif args.trace_log:
            trace_mode = "file"
            trace_log_path = args.trace_log
        else:
            trace_mode = "screen"
            if _prompt_yes_no_block(
                title="Trace 日志文件" if lang == "zh" else "Trace Log File",
                prompt="是否同时写入 Trace 日志文件" if lang == "zh" else "Also write the trace log to a file",
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            ):
                trace_mode = "both"
                trace_log_path = str(default_trace_log_path(config=helpers.build_config_from_args(_with_args(
                    args,
                    season=season,
                    match_type=match_type,
                    runners=runner_tokens,
                    start=start_spec,
                    initial_order=None,
                    iterations=1,
                    seed=seed,
                    workers=1,
                    json=json_output,
                    champion_prediction=None,
                    trace=True,
                    trace_log=None,
                    skill_ablation=False,
                    skill_ablation_runners=None,
                    skill_ablation_detail=False,
                    season_roster_scan=False,
                )), seed=seed))
        _set_wizard_summary("trace", _trace_mode_summary(trace_mode, lang=lang))
        if trace_log_path:
            _set_wizard_summary(
                "trace_path",
                f"{'日志文件' if lang == 'zh' else 'Trace File'} = {trace_log_path}",
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
        trace=trace_mode in {"screen", "both"},
        trace_log=trace_log_path,
        skill_ablation=False,
        skill_ablation_runners=None,
        skill_ablation_detail=False,
        season_roster_scan=False,
    )
    config = helpers.build_config_from_args(interactive_args)
    if simulation_mode == "debug":
        _emit_interactive_trace_log(
            config=config,
            seed=seed,
            helpers=helpers,
            trace_mode=trace_mode,
            trace_log_path=trace_log_path,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
        )
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
    global _ACTIVE_WIZARD_UI
    raw_input_fn = input_fn
    raw_prompt_output_fn = prompt_output_fn
    if getattr(args, "_interactive_auto_entry", False) and not getattr(args, "_interactive_language_explicit", False):
        args = _with_args(
            args,
            interactive_language=_prompt_interactive_language(
                input_fn=raw_input_fn,
                prompt_output_fn=raw_prompt_output_fn,
            ),
        )
    lang = getattr(args, "interactive_language", "zh")
    translate_fn = lambda text: translate_interactive_text(text, lang)
    input_fn = lambda prompt: raw_input_fn(translate_fn(prompt))
    prompt_output_fn = lambda text: raw_prompt_output_fn(translate_fn(text))
    previous_ui = _ACTIVE_WIZARD_UI
    _ACTIVE_WIZARD_UI = InteractiveWizardUI(
        prompt_output_fn=prompt_output_fn,
        lang=lang,
        compact_mode=bool(getattr(sys.stderr, "isatty", lambda: False)()),
    )
    try:
        season = args.season
        if not args.tournament_context_in and not getattr(args, "_season_explicit", False):
            season = int(
                _prompt_choice(
                    "请选择赛季",
                    (
                        ("1", "第1季"),
                        ("2", "第2季"),
                    ),
                    input_fn=input_fn,
                    prompt_output_fn=prompt_output_fn,
                    translate_fn=translate_fn,
                )
            )
            args = _with_args(args, season=season)
        _set_wizard_summary(
            "language",
            "语言 = 中文" if lang == "zh" else "Language = English",
        )
        season_label = f"第{season}季" if lang == "zh" else f"Season {season}"
        _set_wizard_summary("season", f"{'赛季' if lang == 'zh' else 'Season'} = {season_label}")

        if args.champion_prediction or args.tournament_context_in or args.tournament_context_out:
            _set_wizard_summary(
                "analysis",
                "分析 = 赛事冠军预测" if lang == "zh" else "Analysis = Tournament champion prediction",
            )
            return run_interactive_champion_prediction_command(
                args,
                show_progress=show_progress,
                helpers=champion_helpers,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                result_output_fn=result_output_fn,
            )
        if args.match_type or args.runners is not None or args.start or args.initial_order:
            _set_wizard_summary(
                "analysis",
                "分析 = 单场胜率分析" if lang == "zh" else "Analysis = Single-stage win-rate analysis",
            )
            return run_interactive_simulation_command(
                args,
                show_progress=show_progress,
                helpers=simulation_helpers,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )

        season = args.season
        if season != 2:
            _set_wizard_summary(
                "analysis",
                "分析 = 单场胜率分析" if lang == "zh" else "Analysis = Single-stage win-rate analysis",
            )
            prompt_output_fn("当前第1季交互向导先提供单场胜率分析；赛事冠军预测将在后续版本开放。")
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
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
        )
        if analysis_branch == "simulation":
            _set_wizard_summary(
                "analysis",
                "分析 = 单场胜率分析" if lang == "zh" else "Analysis = Single-stage win-rate analysis",
            )
            prompt_output_fn("你正在进入“单场胜率分析”；下一步会先选择具体比赛阶段。")
            return run_interactive_simulation_command(
                args,
                show_progress=show_progress,
                helpers=simulation_helpers,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
            )

        _set_wizard_summary(
            "analysis",
            "分析 = 赛事冠军预测" if lang == "zh" else "Analysis = Tournament champion prediction",
        )
        prompt_output_fn("你正在进入“赛事冠军预测”；下一步会选择单届演示或 Monte Carlo 统计。")
        prediction_mode = _prompt_choice(
            "请选择冠军预测方式",
            (
                ("random", "单届演示（跑 1 届完整赛事）"),
                ("monte-carlo", "Monte Carlo 分析（重复统计夺冠率）"),
            ),
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
        )
        _set_wizard_summary(
            "prediction_mode",
            (
                "冠军方式 = 单届演示"
                if lang == "zh" and prediction_mode == "random"
                else (
                    "冠军方式 = Monte Carlo 分析"
                    if lang == "zh"
                    else (
                        "Champion Mode = Single-run demo"
                        if prediction_mode == "random"
                        else "Champion Mode = Monte Carlo analysis"
                    )
                )
            ),
        )
        entry_mode = _prompt_choice(
            "请选择冠军预测入口",
            (
                ("from-start", "从头开始（完整赛事）"),
                ("from-stage", "从指定阶段开始"),
            ),
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
        )
        _set_wizard_summary("entry_mode", _champion_entry_mode_summary(entry_mode, lang=lang))
        return run_interactive_champion_prediction_command(
            _with_args(args, champion_prediction=prediction_mode, _interactive_entry_mode=entry_mode),
            show_progress=show_progress,
            helpers=champion_helpers,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            result_output_fn=result_output_fn,
        )
    finally:
        _ACTIVE_WIZARD_UI = previous_ui


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
    lang = getattr(args, "interactive_language", "zh")
    translate_fn = lambda text: translate_interactive_text(text, lang)
    raw_input_fn = input_fn
    raw_prompt_output_fn = prompt_output_fn
    input_fn = lambda prompt: raw_input_fn(translate_fn(prompt))
    prompt_output_fn = lambda text: raw_prompt_output_fn(translate_fn(text))
    if not args.json:
        raw_result_output_fn = result_output_fn
        result_output_fn = lambda text: raw_result_output_fn(translate_fn(text))
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

    season_label = f"第{args.season}季" if lang == "zh" else f"Season {args.season}"
    _set_wizard_summary("season", f"{'赛季' if lang == 'zh' else 'Season'} = {season_label}")
    _set_wizard_summary(
        "analysis",
        "分析 = 赛事冠军预测" if lang == "zh" else "Analysis = Tournament champion prediction",
    )

    request = None
    if args.tournament_context_in:
        request = helpers.load_tournament_entry_request(args.tournament_context_in)
        season = request.season
        helpers.validate_champion_prediction_season(season)
        season_label = f"第{season}季" if lang == "zh" else f"Season {season}"
        _set_wizard_summary("season", f"{'赛季' if lang == 'zh' else 'Season'} = {season_label}")
        stage_label = helpers.get_tournament_entry_point_definition(season, request.entry_point).label
        _set_wizard_summary(
            "stage",
            f"{'起始阶段' if lang == 'zh' else 'Start Stage'} = {translate_fn(stage_label)}",
        )
        _set_wizard_summary(
            "context",
            "上下文 = 已载入" if lang == "zh" else "Context = Loaded",
        )
        prompt_output_fn(
            f"已从 {args.tournament_context_in} 载入赛事上下文："
            f"{translate_fn(stage_label)}"
        )
        _emit_champion_entry_guidance(
            season=season,
            entry_point=request.entry_point,
            helpers=helpers,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
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
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        translate_fn=translate_fn,
    )
    _set_wizard_summary(
        "prediction_mode",
        (
            "冠军方式 = 单届演示"
            if lang == "zh" and prediction_mode == "random"
            else (
                "冠军方式 = Monte Carlo 分析"
                if lang == "zh"
                else (
                    "Champion Mode = Single-run demo"
                    if prediction_mode == "random"
                    else "Champion Mode = Monte Carlo analysis"
                )
            )
        ),
    )

    if request is None:
        entry_mode = getattr(args, "_interactive_entry_mode", None)
        if entry_mode is None:
            entry_mode = _prompt_choice(
                "请选择冠军预测入口",
                (
                    ("from-start", "从头开始（完整赛事）"),
                    ("from-stage", "从指定阶段开始"),
                ),
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
        _set_wizard_summary("entry_mode", _champion_entry_mode_summary(entry_mode, lang=lang))
        if entry_mode == "from-start":
            entry_point = helpers.tournament_entry_point_choices(season)[0]
        else:
            entry_options = [
                (key, helpers.get_tournament_entry_point_definition(season, key).label)
                for key in helpers.tournament_entry_point_choices(season)
            ]
            entry_point = _prompt_choice(
                "请选择从哪个阶段开始",
                entry_options,
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
        stage_label = helpers.get_tournament_entry_point_definition(season, entry_point).label
        _set_wizard_summary(
            "stage",
            f"{'起始阶段' if lang == 'zh' else 'Start Stage'} = {translate_fn(stage_label)}",
        )
        _emit_champion_entry_guidance(
            season=season,
            entry_point=entry_point,
            helpers=helpers,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
        )
        _emit_requirement_overview(
            season=season,
            entry_point=entry_point,
            helpers=helpers,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
            translate_fn=translate_fn,
        )
        requirement_values = _collect_derived_entry_inputs(
            helpers=helpers,
            season=season,
            entry_point=entry_point,
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            lang=lang,
            translate_fn=translate_fn,
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
                lang=lang,
                translate_fn=translate_fn,
            )
            if value is not None:
                requirement_values[requirement.key] = value
        request = helpers.build_tournament_entry_request(
            season=season,
            entry_point=entry_point,
            inputs=requirement_values,
        )
        _set_wizard_summary(
            "context",
            "上下文 = 已补齐" if lang == "zh" else "Context = Ready",
        )

    if args.tournament_context_out:
        helpers.save_tournament_entry_request(request, args.tournament_context_out)
        prompt_output_fn(f"赛事上下文已写入：{args.tournament_context_out}")

    seed = args.seed
    if not getattr(args, "_seed_explicit", False):
        seed_text = _prompt_line_block(
            title="随机种子" if lang == "zh" else "Random Seed",
            prompt="请输入随机种子（留空表示不固定）",
            input_fn=input_fn,
            prompt_output_fn=prompt_output_fn,
            translate_fn=translate_fn,
            allow_empty=True,
        )
        seed = int(seed_text) if seed_text else None
    _set_wizard_summary(
        "seed",
        f"{'种子' if lang == 'zh' else 'Seed'} = {seed if seed is not None else ('未固定' if lang == 'zh' else 'unfixed')}",
    )
    json_output = args.json if getattr(args, "_json_explicit", False) else _prompt_yes_no_block(
        title="输出格式" if lang == "zh" else "Output Format",
        prompt="是否输出 JSON 结果",
        input_fn=input_fn,
        prompt_output_fn=prompt_output_fn,
        translate_fn=translate_fn,
    )
    _set_wizard_summary(
        "output",
        "输出 = JSON" if (lang == "zh" and json_output) else ("输出 = 文本" if lang == "zh" else ("Output = JSON" if json_output else "Output = Text")),
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

    iterations = args.iterations
    if not getattr(args, "_iterations_explicit", False):
        iterations = int(
            _prompt_line_block(
                title="模拟次数" if lang == "zh" else "Iterations",
                prompt="请输入 Monte Carlo 模拟次数",
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
        )
    _set_wizard_summary("iterations", f"{'次数' if lang == 'zh' else 'Iterations'} = {iterations}")
    workers = args.workers
    if not getattr(args, "_workers_explicit", False):
        workers = int(
            _prompt_line_block(
                title="并行设置" if lang == "zh" else "Worker Count",
                prompt="请输入 workers 数量（0 表示 CPU 核心数）",
                input_fn=input_fn,
                prompt_output_fn=prompt_output_fn,
                translate_fn=translate_fn,
            )
        )
    _set_wizard_summary("workers", f"{'并行' if lang == 'zh' else 'Workers'} = {workers}")
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
