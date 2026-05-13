from __future__ import annotations

import random
from typing import Any, Sequence

from .runners import (
    CHISA_ID,
    DENIA_ID,
    HIYUKI_ID,
    LYNAE_ID,
    MORNYE_ID,
    NPC_ID,
    RUNNER_NAMES,
    SHOREKEEPER_ID,
    SIGRIKA_ID,
    SKILL_RUNNERS,
    ZANI_ID,
)
from .tracing import TraceContext


LYNAE_DOUBLE_MOVE_CHANCE = 0.6
LYNAE_NO_MOVE_CUTOFF = 0.8
ZANI_ONE_STEP_DICE_CHANCE = 0.5


def skill_enabled(config: object, runner: int) -> bool:
    return skill_enabled_from_set(getattr(config, "disabled_skills", frozenset()), runner)


def skill_enabled_from_set(disabled_skills: frozenset[int], runner: int) -> bool:
    return runner in SKILL_RUNNERS and runner not in disabled_skills


def record_skill_success(skill_state: Any | None, runner: int, amount: int = 1) -> None:
    if skill_state is None or amount <= 0:
        return
    skill_state.success_counts[runner] = skill_state.success_counts.get(runner, 0) + amount


def mark_sigrika_debuffs(
    *,
    runners: Sequence[int],
    progress: dict[int, int],
    grid: dict[int, Sequence[int]],
    round_number: int = 2,
    skip_first_round: bool = False,
    disabled_skills: frozenset[int] = frozenset(),
    trace: TraceContext = False,
) -> set[int]:
    if SIGRIKA_ID not in runners or not skill_enabled_from_set(disabled_skills, SIGRIKA_ID):
        return set()
    if round_number == 1 and skip_first_round:
        if trace:
            _log_timing(trace, "回合开始", f"{_format_runner(SIGRIKA_ID)}第一轮不发动技能")
            _log_block(trace, f"{_format_runner(SIGRIKA_ID)}技能不发动：", "原因：随机堆叠开局第一轮不发动")
        return set()
    ranking = _current_rank(runners, progress, grid)
    sigrika_index = ranking.index(SIGRIKA_ID)
    targets = tuple(ranking[max(0, sigrika_index - 2) : sigrika_index])
    if trace:
        _log_timing(trace, "回合开始", f"{_format_runner(SIGRIKA_ID)}标记排名紧邻且高于自己的至多两名角色")
        _log_block(
            trace,
            f"{_format_runner(SIGRIKA_ID)}技能判定：",
            "NPC参与排名：否",
            f"名次（前→后）：{_format_runner_arrow_list(ranking)}",
            f"标记目标：{_format_cell(targets) if targets else '无'}",
            "效果：被标记角色本轮移动总步数-1，最低为1步",
        )
    return set(targets)


def apply_sigrika_debuff(
    *,
    player: int,
    total_steps: int,
    debuffed: set[int],
    skill_state: Any | None = None,
    trace: TraceContext = False,
) -> int:
    if player not in debuffed:
        return total_steps
    if total_steps <= 0:
        if trace:
            _log_timing(trace, "移动结算前", f"{_format_runner(SIGRIKA_ID)}的减速标记对{_format_runner(player)}生效")
            _log_block(trace, f"{_format_runner(SIGRIKA_ID)}减速未改变步数：", "原因：目标本回合无法移动")
        return 0
    adjusted_steps = max(1, total_steps - 1)
    if adjusted_steps < total_steps:
        record_skill_success(skill_state, SIGRIKA_ID)
    if trace:
        _log_timing(trace, "移动结算前", f"{_format_runner(SIGRIKA_ID)}的减速标记对{_format_runner(player)}生效")
        _log_block(
            trace,
            f"{_format_runner(SIGRIKA_ID)}减速生效：",
            f"原总步数：{total_steps}",
            f"减速后总步数：{adjusted_steps}",
        )
    return adjusted_steps


def check_chisa_skill(
    skill_state: Any,
    dice: int,
    round_dice: dict[int, int],
    trace: TraceContext = False,
) -> int:
    active = chisa_has_lowest_dice(dice, round_dice)
    log_chisa_round_check(dice, round_dice, active, trace)
    return apply_chisa_bonus(skill_state, active, trace)


def chisa_has_lowest_dice(dice: int, round_dice: dict[int, int]) -> bool:
    return dice == min(round_dice.values())


def log_chisa_round_check(
    dice: int,
    round_dice: dict[int, int],
    active: bool,
    trace: TraceContext = False,
) -> None:
    if not trace:
        return
    _log_timing(trace, "本轮骰点生成后", f"{_format_runner(CHISA_ID)}检查自身骰点是否为所有行动单位中的最小值")
    lowest = min(round_dice.values())
    if active:
        _log_block(
            trace,
            f"{_format_runner(CHISA_ID)}技能判定通过：",
            f"本轮最低骰点：{lowest}",
            f"自身骰点：{dice}",
            "本回合前进时将额外+2步",
        )
        return
    _log_block(
        trace,
        f"{_format_runner(CHISA_ID)}技能判定未通过：",
        f"本轮最低骰点：{lowest}",
        f"自身骰点：{dice}",
    )


def apply_chisa_bonus(
    skill_state: Any,
    active: bool,
    trace: TraceContext = False,
) -> int:
    if active:
        record_skill_success(skill_state, CHISA_ID)
        if trace:
            _log_block(trace, f"{_format_runner(CHISA_ID)}技能生效：", "效果：本回合额外+2步")
        return 2
    if trace:
        _log_block(trace, f"{_format_runner(CHISA_ID)}技能未生效：", "原因：投骰结束判定未通过")
    return 0


def check_denia_skill(
    skill_state: Any,
    dice: int,
    trace: TraceContext = False,
) -> int:
    if trace:
        _log_timing(trace, "骰子后", f"{_format_runner(DENIA_ID)}检查本轮骰点是否与上一轮相同")
    previous = skill_state.denia_last_dice
    skill_state.denia_last_dice = dice
    if previous is None:
        if trace:
            _log_block(trace, f"{_format_runner(DENIA_ID)}技能不判定：", "原因：没有上一轮骰点记录")
        return 0
    if previous == dice:
        record_skill_success(skill_state, DENIA_ID)
        if trace:
            _log_block(
                trace,
                f"{_format_runner(DENIA_ID)}技能触发：",
                f"上一轮骰点：{previous}",
                f"本轮骰点：{dice}",
                "效果：额外+2步",
            )
        return 2
    if trace:
        _log_block(
            trace,
            f"{_format_runner(DENIA_ID)}技能未触发：",
            f"上一轮骰点：{previous}",
            f"本轮骰点：{dice}",
        )
    return 0


def apply_lynae_skill(
    skill_state: Any,
    rng: random.Random,
    *,
    dice: int,
    total_steps: int,
    trace: TraceContext = False,
) -> tuple[int, int]:
    if trace:
        _log_timing(trace, "移动结算前", f"{_format_runner(LYNAE_ID)}进行60%双倍点数、20%无法移动判定")
    roll = rng.random()
    if roll < LYNAE_DOUBLE_MOVE_CHANCE:
        adjusted = total_steps + dice
        record_skill_success(skill_state, LYNAE_ID)
        if trace:
            _log_block(
                trace,
                f"{_format_runner(LYNAE_ID)}技能触发：",
                "结果：双倍点数移动",
                f"原总步数：{total_steps}",
                f"修正后总步数：{adjusted}",
            )
        return adjusted, dice
    if roll < LYNAE_NO_MOVE_CUTOFF:
        if trace:
            _log_block(
                trace,
                f"{_format_runner(LYNAE_ID)}技能触发但无法移动：",
                "结果：本回合无法移动",
                f"原总步数：{total_steps}",
                "修正后总步数：0",
            )
        return 0, -total_steps
    if trace:
        _log_block(trace, f"{_format_runner(LYNAE_ID)}技能未触发：", "结果：按原总步数移动")
    return total_steps, 0


def check_hiyuki_bonus(skill_state: Any, trace: TraceContext = False) -> int:
    if trace:
        _log_timing(trace, "行动开始", f"{_format_runner(HIYUKI_ID)}检查与NPC相遇后获得的额外步数")
    if skill_state.hiyuki_bonus_steps <= 0:
        if trace:
            _log_block(trace, f"{_format_runner(HIYUKI_ID)}技能未生效：", "原因：尚未与NPC相遇")
        return 0
    if trace:
        _log_block(
            trace,
            f"{_format_runner(HIYUKI_ID)}技能生效：",
            "当前状态：已与NPC相遇",
            "效果：额外+1步",
        )
    return 1


def roll_dice(
    player: int,
    rng: random.Random,
    *,
    config: object | None = None,
    skill_state: Any | None = None,
) -> int:
    if player == MORNYE_ID and (config is None or skill_enabled(config, MORNYE_ID)):
        if skill_state is None:
            return 3
        dice = skill_state.mornye_next_dice
        skill_state.mornye_next_dice = 3 if dice == 1 else dice - 1
        record_skill_success(skill_state, MORNYE_ID)
        return dice
    if player == SHOREKEEPER_ID and (config is None or skill_enabled(config, SHOREKEEPER_ID)):
        record_skill_success(skill_state, SHOREKEEPER_ID)
        return rng.randint(2, 3)
    if player == ZANI_ID:
        return 1 if rng.random() < ZANI_ONE_STEP_DICE_CHANCE else 3
    return rng.randint(1, 3)


def roll_round_dice(
    player_order: Sequence[int],
    rng: random.Random,
    *,
    config: object,
    skill_state: Any,
) -> dict[int, int]:
    return {
        player: rng.randint(1, 6) if player == NPC_ID else roll_dice(player, rng, config=config, skill_state=skill_state)
        for player in player_order
    }


def _current_rank(runners: Sequence[int], progress: dict[int, int], grid: dict[int, Sequence[int]]) -> list[int]:
    cell_index: dict[int, int] = {}
    for cell in grid.values():
        for idx, runner in enumerate(cell):
            if runner != NPC_ID:
                cell_index[runner] = idx
    return sorted(runners, key=lambda runner: (-progress[runner], cell_index.get(runner, 9999)))


def _format_runner(runner: int) -> str:
    if runner == NPC_ID:
        return "NPC"
    return RUNNER_NAMES.get(runner, f"角色{runner}")


def _format_cell(cell: Sequence[int]) -> str:
    return "[" + ", ".join(_format_runner(runner) for runner in cell) + "]"


def _format_runner_arrow_list(runners: Sequence[int]) -> str:
    return " -> ".join(_format_runner(runner) for runner in runners)


def _log(enabled: TraceContext, message: str) -> None:
    if not enabled:
        return
    if hasattr(enabled, "write_line"):
        enabled.write_line(message)
    else:
        print(message)


def _log_timing(enabled: TraceContext, timing: str, message: str) -> None:
    _log(enabled, f"【判定时机：{timing}】")
    _log(enabled, f"  {message}")
    _log(enabled, "")


def _log_block(enabled: TraceContext, title: str, *lines: str) -> None:
    _log(enabled, title)
    for line in lines:
        _log(enabled, f"  {line}")
    _log(enabled, "")
