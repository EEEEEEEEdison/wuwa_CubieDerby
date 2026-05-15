from __future__ import annotations

import math
import random
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from cubie_derby_core.match_types import (
    MatchTypeRule,
    build_group_round_two_start_spec,
    effective_qualify_cutoff,
    eliminated_runners_for_rule,
    get_match_type_rule,
    qualified_runners_for_rule,
    resolve_match_start_spec,
)
from cubie_derby_core.runners import RUNNER_NAMES

BuildRaceConfigFn = Callable[..., Any]
DeriveSeedFn = Callable[[int, int], int]
ProgressBatchSizeFn = Callable[[int], int]
SeasonRunnerPoolFn = Callable[[int], Sequence[int]]
SimulateRaceFn = Callable[[Any, random.Random], Any]


@dataclass(frozen=True)
class StageResult:
    title: str
    match_type: str
    match_label: str
    entrants: tuple[int, ...]
    start_spec: str
    ranking: tuple[int, ...]
    qualified_runners: tuple[int, ...] = ()
    eliminated_runners: tuple[int, ...] = ()
    next_stage_start_spec: str | None = None
    show_qualify_stats: bool = True


@dataclass(frozen=True)
class TournamentResult:
    season: int
    stages: tuple[StageResult, ...]
    champion: int
    elapsed_seconds: float | None = None
    start_entry_point: str | None = None
    start_entry_label: str | None = None
    remaining_stage_labels: tuple[str, ...] = ()
    input_context: tuple["TournamentInputSnapshot", ...] = ()


@dataclass(frozen=True)
class TournamentPhaseDefinition:
    key: str
    label: str
    match_type: str
    group_count: int
    group_size: int
    entrants_count: int
    seeded_from_ranking_order: bool = False

    @property
    def stage_count(self) -> int:
        return self.group_count


@dataclass(frozen=True)
class TournamentStartRequest:
    season: int
    start_phase: str
    entrants: tuple[int, ...] = ()
    grouped_entrants: tuple[tuple[int, ...], ...] | None = None


@dataclass(frozen=True)
class TournamentPlan:
    season: int
    start_phase: str
    entrants: tuple[int, ...]
    grouped_entrants: tuple[tuple[int, ...], ...] | None
    phases: tuple[TournamentPhaseDefinition, ...]

    @property
    def stage_count(self) -> int:
        return sum(phase.stage_count for phase in self.phases)


@dataclass(frozen=True)
class TournamentInputRequirement:
    key: str
    label: str
    kind: str
    runner_count: int
    description: str
    ordered: bool = False
    optional: bool = False
    group_count: int | None = None
    group_size: int | None = None


@dataclass(frozen=True)
class TournamentEntryPointDefinition:
    key: str
    label: str
    phase_key: str
    requirements: tuple[TournamentInputRequirement, ...]


@dataclass(frozen=True)
class TournamentEntryRequest:
    season: int
    entry_point: str
    inputs: dict[str, tuple[int, ...] | tuple[tuple[int, ...], ...]]


@dataclass(frozen=True)
class TournamentInputSnapshot:
    key: str
    label: str
    kind: str
    ordered: bool
    runners: tuple[int, ...] = ()
    groups: tuple[tuple[int, ...], ...] = ()


SEASON2_TOURNAMENT_PHASES: dict[str, TournamentPhaseDefinition] = {
    "group-round-1": TournamentPhaseDefinition(
        key="group-round-1",
        label="小组赛第一轮",
        match_type="group-round-1",
        group_count=3,
        group_size=6,
        entrants_count=18,
    ),
    "group-round-2": TournamentPhaseDefinition(
        key="group-round-2",
        label="小组赛第二轮",
        match_type="group-round-2",
        group_count=3,
        group_size=6,
        entrants_count=18,
        seeded_from_ranking_order=True,
    ),
    "elimination": TournamentPhaseDefinition(
        key="elimination",
        label="淘汰赛",
        match_type="elimination",
        group_count=2,
        group_size=6,
        entrants_count=12,
    ),
    "losers-round-1": TournamentPhaseDefinition(
        key="losers-round-1",
        label="败者组第一轮",
        match_type="losers-bracket",
        group_count=1,
        group_size=6,
        entrants_count=6,
    ),
    "winners-round-2": TournamentPhaseDefinition(
        key="winners-round-2",
        label="胜者组第二轮",
        match_type="winners-bracket",
        group_count=1,
        group_size=6,
        entrants_count=6,
    ),
    "losers-round-2": TournamentPhaseDefinition(
        key="losers-round-2",
        label="败者组第二轮",
        match_type="losers-bracket",
        group_count=1,
        group_size=6,
        entrants_count=6,
    ),
    "grand-final": TournamentPhaseDefinition(
        key="grand-final",
        label="总决赛",
        match_type="grand-final",
        group_count=1,
        group_size=6,
        entrants_count=6,
    ),
}

SEASON2_TOURNAMENT_FLOW: tuple[str, ...] = (
    "group-round-1",
    "group-round-2",
    "elimination",
    "losers-round-1",
    "winners-round-2",
    "losers-round-2",
    "grand-final",
)

TOURNAMENT_PHASE_ALIASES = {
    "group-round-1": "group-round-1",
    "小组赛第一轮": "group-round-1",
    "group-round-2": "group-round-2",
    "小组赛第二轮": "group-round-2",
    "elimination": "elimination",
    "淘汰赛": "elimination",
    "losers-round-1": "losers-round-1",
    "losers-bracket": "losers-round-1",
    "败者组": "losers-round-1",
    "败者组第一轮": "losers-round-1",
    "winners-round-2": "winners-round-2",
    "winners-bracket": "winners-round-2",
    "胜者组": "winners-round-2",
    "胜者组第二轮": "winners-round-2",
    "losers-round-2": "losers-round-2",
    "败者组第二轮": "losers-round-2",
    "grand-final": "grand-final",
    "总决赛": "grand-final",
}

SEASON2_TOURNAMENT_ENTRY_FLOW: tuple[str, ...] = (
    "group-a-round-1",
    "group-a-round-2",
    "group-b-round-1",
    "group-b-round-2",
    "group-c-round-1",
    "group-c-round-2",
    "elimination-a",
    "elimination-b",
    "losers-round-1",
    "winners-round-2",
    "losers-round-2",
    "grand-final",
)

SEASON2_TOURNAMENT_ENTRY_POINTS: dict[str, TournamentEntryPointDefinition] = {
    "group-a-round-1": TournamentEntryPointDefinition(
        key="group-a-round-1",
        label="小组A第一轮",
        phase_key="group-round-1",
        requirements=(
            TournamentInputRequirement(
                key="season-roster",
                label="本届参赛角色（18名）",
                kind="entrants",
                runner_count=18,
                description="提供本届赛事全部 18 名参赛角色；若不额外指定分组，系统会随机分配到小组 A/B/C。",
            ),
            TournamentInputRequirement(
                key="group-stage-groups",
                label="小组赛 A/B/C 分组（3组×6名，可选）",
                kind="grouped-entrants",
                runner_count=18,
                description="如果你已经确定了小组赛分组，可以直接给出 A/B/C 三组各 6 人；否则系统会按 seed 随机分组。",
                optional=True,
                group_count=3,
                group_size=6,
            ),
        ),
    ),
    "group-a-round-2": TournamentEntryPointDefinition(
        key="group-a-round-2",
        label="小组A第二轮",
        phase_key="group-round-2",
        requirements=(
            TournamentInputRequirement(
                key="group-a-round-2-entrants",
                label="小组A第二轮参赛顺序（6名）",
                kind="ranking",
                runner_count=6,
                description="按小组 A 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。",
                ordered=True,
            ),
            TournamentInputRequirement(
                key="group-b-round-1-entrants",
                label="小组B第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 B 的两轮比赛。",
            ),
            TournamentInputRequirement(
                key="group-c-round-1-entrants",
                label="小组C第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 C 的两轮比赛。",
            ),
        ),
    ),
    "group-b-round-1": TournamentEntryPointDefinition(
        key="group-b-round-1",
        label="小组B第一轮",
        phase_key="group-round-1",
        requirements=(
            TournamentInputRequirement(
                key="group-a-round-2-qualified",
                label="小组A第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 A 已经结束，需要补齐这 4 个晋级名额，后续才能拼出淘汰赛阶段的 12 人名单。",
            ),
            TournamentInputRequirement(
                key="group-b-round-1-entrants",
                label="小组B第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 B 的两轮比赛。",
            ),
            TournamentInputRequirement(
                key="group-c-round-1-entrants",
                label="小组C第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 C 的两轮比赛。",
            ),
        ),
    ),
    "group-b-round-2": TournamentEntryPointDefinition(
        key="group-b-round-2",
        label="小组B第二轮",
        phase_key="group-round-2",
        requirements=(
            TournamentInputRequirement(
                key="group-a-round-2-qualified",
                label="小组A第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 A 已经结束，需要补齐这 4 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="group-b-round-2-entrants",
                label="小组B第二轮参赛顺序（6名）",
                kind="ranking",
                runner_count=6,
                description="按小组 B 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。",
                ordered=True,
            ),
            TournamentInputRequirement(
                key="group-c-round-1-entrants",
                label="小组C第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 C 的两轮比赛。",
            ),
        ),
    ),
    "group-c-round-1": TournamentEntryPointDefinition(
        key="group-c-round-1",
        label="小组C第一轮",
        phase_key="group-round-1",
        requirements=(
            TournamentInputRequirement(
                key="group-a-round-2-qualified",
                label="小组A第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 A 已经结束，需要补齐这 4 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="group-b-round-2-qualified",
                label="小组B第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 B 已经结束，需要补齐这 4 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="group-c-round-1-entrants",
                label="小组C第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟小组 C 的两轮比赛。",
            ),
        ),
    ),
    "group-c-round-2": TournamentEntryPointDefinition(
        key="group-c-round-2",
        label="小组C第二轮",
        phase_key="group-round-2",
        requirements=(
            TournamentInputRequirement(
                key="group-a-round-2-qualified",
                label="小组A第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 A 已经结束，需要补齐这 4 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="group-b-round-2-qualified",
                label="小组B第二轮晋级角色（前4名）",
                kind="qualified",
                runner_count=4,
                description="小组 B 已经结束，需要补齐这 4 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="group-c-round-2-entrants",
                label="小组C第二轮参赛顺序（6名）",
                kind="ranking",
                runner_count=6,
                description="按小组 C 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。",
                ordered=True,
            ),
        ),
    ),
    "elimination-a": TournamentEntryPointDefinition(
        key="elimination-a",
        label="淘汰赛A",
        phase_key="elimination",
        requirements=(
            TournamentInputRequirement(
                key="elimination-a-entrants",
                label="淘汰赛A参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="12 名小组赛晋级者如何分到淘汰赛 A/B 两组，需要在这里确定一半名单。",
            ),
            TournamentInputRequirement(
                key="elimination-b-entrants",
                label="淘汰赛B参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="补齐淘汰赛另一组名单，后续才能继续拼接胜者组和败者组。",
            ),
        ),
    ),
    "elimination-b": TournamentEntryPointDefinition(
        key="elimination-b",
        label="淘汰赛B",
        phase_key="elimination",
        requirements=(
            TournamentInputRequirement(
                key="elimination-a-ranking",
                label="淘汰赛A完整排名（6名）",
                kind="ranking",
                runner_count=6,
                description="用于确定胜者组和败者组各自来自淘汰赛 A 的 3 个席位。",
                ordered=True,
            ),
            TournamentInputRequirement(
                key="elimination-b-entrants",
                label="淘汰赛B参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟淘汰赛 B。",
            ),
        ),
    ),
    "losers-round-1": TournamentEntryPointDefinition(
        key="losers-round-1",
        label="败者组第一轮",
        phase_key="losers-round-1",
        requirements=(
            TournamentInputRequirement(
                key="losers-round-1-entrants",
                label="败者组第一轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="这是两场淘汰赛后落入败者组的 6 名角色。",
            ),
            TournamentInputRequirement(
                key="winners-round-2-entrants",
                label="胜者组参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="这是两场淘汰赛后进入胜者组的 6 名角色。",
            ),
        ),
    ),
    "winners-round-2": TournamentEntryPointDefinition(
        key="winners-round-2",
        label="胜者组",
        phase_key="winners-round-2",
        requirements=(
            TournamentInputRequirement(
                key="losers-round-1-qualified",
                label="败者组第一轮晋级角色（前3名）",
                kind="qualified",
                runner_count=3,
                description="后续败者组第二轮需要用到这 3 个晋级名额。",
            ),
            TournamentInputRequirement(
                key="winners-round-2-entrants",
                label="胜者组参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟胜者组并锁定总决赛的前 3 席。",
            ),
        ),
    ),
    "losers-round-2": TournamentEntryPointDefinition(
        key="losers-round-2",
        label="败者组第二轮",
        phase_key="losers-round-2",
        requirements=(
            TournamentInputRequirement(
                key="winners-round-2-qualified",
                label="胜者组直通总决赛角色（前3名）",
                kind="qualified",
                runner_count=3,
                description="这 3 名角色会直接占据总决赛的一半席位，后续需要与败者组第二轮前 3 名合并。",
            ),
            TournamentInputRequirement(
                key="losers-round-2-entrants",
                label="败者组第二轮参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="用于继续模拟败者组第二轮，并决出剩余 3 个总决赛席位。",
            ),
        ),
    ),
    "grand-final": TournamentEntryPointDefinition(
        key="grand-final",
        label="总决赛",
        phase_key="grand-final",
        requirements=(
            TournamentInputRequirement(
                key="grand-final-entrants",
                label="总决赛参赛角色（6名）",
                kind="entrants",
                runner_count=6,
                description="从总决赛开始时，冠军预测会退化成单阶段夺冠预测。",
            ),
        ),
    ),
}

TOURNAMENT_ENTRY_ALIASES = {
    "group-a-round-1": "group-a-round-1",
    "小组a第一轮": "group-a-round-1",
    "小组赛a第一轮": "group-a-round-1",
    "group-a-round-2": "group-a-round-2",
    "小组a第二轮": "group-a-round-2",
    "小组赛a第二轮": "group-a-round-2",
    "group-b-round-1": "group-b-round-1",
    "小组b第一轮": "group-b-round-1",
    "小组赛b第一轮": "group-b-round-1",
    "group-b-round-2": "group-b-round-2",
    "小组b第二轮": "group-b-round-2",
    "小组赛b第二轮": "group-b-round-2",
    "group-c-round-1": "group-c-round-1",
    "小组c第一轮": "group-c-round-1",
    "小组赛c第一轮": "group-c-round-1",
    "group-c-round-2": "group-c-round-2",
    "小组c第二轮": "group-c-round-2",
    "小组赛c第二轮": "group-c-round-2",
    "elimination-a": "elimination-a",
    "淘汰赛a": "elimination-a",
    "elimination-b": "elimination-b",
    "淘汰赛b": "elimination-b",
    "losers-round-1": "losers-round-1",
    "败者组第一轮": "losers-round-1",
    "winners-round-2": "winners-round-2",
    "胜者组": "winners-round-2",
    "胜者组第二轮": "winners-round-2",
    "losers-round-2": "losers-round-2",
    "败者组第二轮": "losers-round-2",
    "grand-final": "grand-final",
    "总决赛": "grand-final",
}


@dataclass(frozen=True)
class ChampionPredictionRow:
    runner: int
    name: str
    championships: int
    champion_rate: float


@dataclass(frozen=True)
class ChampionPredictionSummary:
    season: int
    iterations: int
    rows: tuple[ChampionPredictionRow, ...]
    elapsed_seconds: float | None = None
    start_entry_point: str | None = None
    start_entry_label: str | None = None
    remaining_stage_labels: tuple[str, ...] = ()
    input_context: tuple[TournamentInputSnapshot, ...] = ()

    @property
    def best(self) -> ChampionPredictionRow:
        return max(self.rows, key=lambda row: row.champion_rate)


class ChampionPredictionAccumulator:
    def __init__(self, roster: Sequence[int]) -> None:
        self.roster = tuple(roster)
        self.index = {runner: i for i, runner in enumerate(self.roster)}
        self.iterations = 0
        self.championships = [0] * len(self.roster)

    def add(self, champion: int) -> None:
        self.iterations += 1
        self.championships[self.index[champion]] += 1

    def merge(self, other: "ChampionPredictionAccumulator") -> None:
        if self.roster != other.roster:
            raise ValueError("cannot merge champion accumulators for different rosters")
        self.iterations += other.iterations
        for index in range(len(self.roster)):
            self.championships[index] += other.championships[index]

    def to_summary(
        self,
        *,
        season: int,
        elapsed_seconds: float | None = None,
        start_entry_point: str | None = None,
        start_entry_label: str | None = None,
        remaining_stage_labels: tuple[str, ...] = (),
        input_context: tuple["TournamentInputSnapshot", ...] = (),
    ) -> ChampionPredictionSummary:
        rows = []
        total = self.iterations
        for runner in self.roster:
            championships = self.championships[self.index[runner]]
            rows.append(
                ChampionPredictionRow(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    championships=championships,
                    champion_rate=championships / total if total else math.nan,
                )
            )
        return ChampionPredictionSummary(
            season=season,
            iterations=total,
            rows=tuple(rows),
            elapsed_seconds=elapsed_seconds,
            start_entry_point=start_entry_point,
            start_entry_label=start_entry_label,
            remaining_stage_labels=remaining_stage_labels,
            input_context=input_context,
        )


def tournament_phase_choices(season: int) -> tuple[str, ...]:
    validate_champion_prediction_season(season)
    if season == 2:
        return SEASON2_TOURNAMENT_FLOW
    raise ValueError(f"season {season} does not support tournament phases yet")


def normalize_tournament_phase(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("tournament phase cannot be empty")
    alias = TOURNAMENT_PHASE_ALIASES.get(normalized)
    if alias is not None:
        return alias
    alias = TOURNAMENT_PHASE_ALIASES.get(value.strip())
    if alias is not None:
        return alias
    raise ValueError(f"unknown tournament phase: {value}")


def get_tournament_phase_definition(season: int, phase: str) -> TournamentPhaseDefinition:
    validate_champion_prediction_season(season)
    key = normalize_tournament_phase(phase)
    if season == 2:
        return SEASON2_TOURNAMENT_PHASES[key]
    raise ValueError(f"season {season} does not support tournament phases yet")


def remaining_tournament_phases(season: int, start_phase: str) -> tuple[TournamentPhaseDefinition, ...]:
    phase = get_tournament_phase_definition(season, start_phase)
    flow = tournament_phase_choices(season)
    start_index = flow.index(phase.key)
    return tuple(SEASON2_TOURNAMENT_PHASES[key] for key in flow[start_index:])


def tournament_entry_point_choices(season: int) -> tuple[str, ...]:
    validate_champion_prediction_season(season)
    if season == 2:
        return SEASON2_TOURNAMENT_ENTRY_FLOW
    raise ValueError(f"season {season} does not support tournament entry points yet")


def normalize_tournament_entry_point(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("tournament entry point cannot be empty")
    alias = TOURNAMENT_ENTRY_ALIASES.get(normalized)
    if alias is not None:
        return alias
    alias = TOURNAMENT_ENTRY_ALIASES.get(value.strip())
    if alias is not None:
        return alias
    raise ValueError(f"unknown tournament entry point: {value}")


def get_tournament_entry_point_definition(season: int, entry_point: str) -> TournamentEntryPointDefinition:
    validate_champion_prediction_season(season)
    key = normalize_tournament_entry_point(entry_point)
    if season == 2:
        return SEASON2_TOURNAMENT_ENTRY_POINTS[key]
    raise ValueError(f"season {season} does not support tournament entry points yet")


def tournament_entry_requirements(season: int, entry_point: str) -> tuple[TournamentInputRequirement, ...]:
    return get_tournament_entry_point_definition(season, entry_point).requirements


def tournament_entry_remaining_stage_labels(season: int, entry_point: str) -> tuple[str, ...]:
    definition = get_tournament_entry_point_definition(season, entry_point)
    flow = tournament_entry_point_choices(season)
    start_index = flow.index(definition.key)
    return tuple(
        get_tournament_entry_point_definition(season, key).label
        for key in flow[start_index:]
    )


def normalize_tournament_input_value(
    requirement: TournamentInputRequirement,
    value: Sequence[int] | Sequence[Sequence[int]],
) -> tuple[int, ...] | tuple[tuple[int, ...], ...]:
    if requirement.kind == "grouped-entrants":
        groups = tuple(tuple(group) for group in value)  # type: ignore[arg-type]
        if requirement.group_count is None or requirement.group_size is None:
            raise ValueError(f"{requirement.label} is missing group validation metadata")
        if len(groups) != requirement.group_count:
            raise ValueError(
                f"{requirement.label} requires exactly {requirement.group_count} groups, got {len(groups)}"
            )
        if any(len(group) != requirement.group_size for group in groups):
            raise ValueError(
                f"{requirement.label} requires groups of exactly {requirement.group_size} runners"
            )
        flattened = tuple(runner for group in groups for runner in group)
        if len(flattened) != requirement.runner_count:
            raise ValueError(
                f"{requirement.label} requires exactly {requirement.runner_count} runners, got {len(flattened)}"
            )
        if len(set(flattened)) != len(flattened):
            raise ValueError(f"{requirement.label} contains duplicate runners")
        return groups
    runners = tuple(value)  # type: ignore[arg-type]
    if len(runners) != requirement.runner_count:
        raise ValueError(
            f"{requirement.label} requires exactly {requirement.runner_count} runners, got {len(runners)}"
        )
    if len(set(runners)) != len(runners):
        raise ValueError(f"{requirement.label} contains duplicate runners")
    return runners


def build_tournament_entry_request(
    *,
    season: int,
    entry_point: str,
    inputs: dict[str, Sequence[int] | Sequence[Sequence[int]]],
) -> TournamentEntryRequest:
    definition = get_tournament_entry_point_definition(season, entry_point)
    normalized_inputs: dict[str, tuple[int, ...] | tuple[tuple[int, ...], ...]] = {}
    season_roster: tuple[int, ...] | None = None
    grouped_flattened: tuple[int, ...] | None = None
    all_runners: list[int] = []
    for requirement in definition.requirements:
        raw_value = inputs.get(requirement.key)
        if raw_value is None:
            if requirement.optional:
                continue
            raise ValueError(f"missing required tournament input: {requirement.label}")
        normalized_value = normalize_tournament_input_value(requirement, raw_value)
        normalized_inputs[requirement.key] = normalized_value
        if requirement.key == "season-roster":
            season_roster = normalized_value  # type: ignore[assignment]
        elif requirement.key == "group-stage-groups":
            grouped_flattened = tuple(runner for group in normalized_value for runner in group)  # type: ignore[misc]
        if requirement.kind == "grouped-entrants":
            if requirement.key != "group-stage-groups":
                all_runners.extend(runner for group in normalized_value for runner in group)  # type: ignore[misc]
        else:
            all_runners.extend(normalized_value)  # type: ignore[arg-type]
    if season_roster is not None and grouped_flattened is not None:
        if set(season_roster) != set(grouped_flattened):
            raise ValueError("小组赛分组与本届参赛角色名单不一致")
    if len(set(all_runners)) != len(all_runners):
        raise ValueError(f"{definition.label} inputs contain duplicate runners across requirements")
    return TournamentEntryRequest(
        season=season,
        entry_point=definition.key,
        inputs=normalized_inputs,
    )


def tournament_entry_input_context(request: TournamentEntryRequest) -> tuple[TournamentInputSnapshot, ...]:
    definition = get_tournament_entry_point_definition(request.season, request.entry_point)
    snapshots: list[TournamentInputSnapshot] = []
    for requirement in definition.requirements:
        value = request.inputs.get(requirement.key)
        if value is None:
            continue
        if requirement.kind == "grouped-entrants":
            snapshots.append(
                TournamentInputSnapshot(
                    key=requirement.key,
                    label=requirement.label,
                    kind=requirement.kind,
                    ordered=requirement.ordered,
                    groups=tuple(tuple(group) for group in value),  # type: ignore[arg-type]
                )
            )
        else:
            snapshots.append(
                TournamentInputSnapshot(
                    key=requirement.key,
                    label=requirement.label,
                    kind=requirement.kind,
                    ordered=requirement.ordered,
                    runners=tuple(value),  # type: ignore[arg-type]
                )
            )
    return tuple(snapshots)


def resolve_tournament_start_entrants(request: TournamentStartRequest) -> tuple[int, ...]:
    if request.grouped_entrants is not None:
        flattened = tuple(runner for group in request.grouped_entrants for runner in group)
        if request.entrants and tuple(request.entrants) != flattened:
            raise ValueError("grouped entrants do not match flat entrants")
        return flattened
    if not request.entrants:
        raise ValueError("tournament start request requires entrants")
    return tuple(request.entrants)


def build_tournament_plan(request: TournamentStartRequest) -> TournamentPlan:
    phase = get_tournament_phase_definition(request.season, request.start_phase)
    entrants = resolve_tournament_start_entrants(request)
    if len(entrants) != phase.entrants_count:
        raise ValueError(
            f"{phase.label} requires exactly {phase.entrants_count} entrants, got {len(entrants)}"
        )
    if len(set(entrants)) != len(entrants):
        raise ValueError("tournament start entrants contain duplicates")
    grouped_entrants = request.grouped_entrants
    if grouped_entrants is not None:
        if len(grouped_entrants) != phase.group_count:
            raise ValueError(
                f"{phase.label} requires exactly {phase.group_count} groups, got {len(grouped_entrants)}"
            )
        if any(len(group) != phase.group_size for group in grouped_entrants):
            raise ValueError(
                f"{phase.label} requires groups of exactly {phase.group_size} entrants"
            )
    return TournamentPlan(
        season=request.season,
        start_phase=phase.key,
        entrants=entrants,
        grouped_entrants=grouped_entrants,
        phases=remaining_tournament_phases(request.season, phase.key),
    )


def format_runner(runner: int) -> str:
    return RUNNER_NAMES.get(runner, "NPC" if runner < 0 else str(runner))


def format_runner_list(runners: Sequence[int]) -> str:
    return ", ".join(format_runner(runner) for runner in runners)


def format_runner_arrow_list(runners: Sequence[int]) -> str:
    return " -> ".join(format_runner(runner) for runner in runners)


def display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def pad_display_width(text: str, width: int, *, align: str = "left") -> str:
    padding = max(0, width - display_width(text))
    if align == "right":
        return " " * padding + text
    if align == "left":
        return text + " " * padding
    raise ValueError(f"unknown alignment: {align}")


def format_table_row(cells: Sequence[str], widths: Sequence[int], aligns: Sequence[str]) -> str:
    parts = [
        pad_display_width(cell, width, align=align)
        for cell, width, align in zip(cells, widths, aligns, strict=True)
    ]
    return "  ".join(parts)


def format_table_separator(widths: Sequence[int]) -> str:
    return "  ".join("-" * width for width in widths)


def format_elapsed(elapsed_seconds: float | None) -> str:
    if elapsed_seconds is None:
        return "未统计"
    if elapsed_seconds < 1:
        return f"{elapsed_seconds * 1000:.0f} ms"
    return f"{elapsed_seconds:.2f} 秒"


def format_rate(rate: float | None) -> str:
    if rate is None:
        return "未统计"
    return f"{rate:,.0f} 局/秒"


def format_runtime_status_line(label: str, value: str) -> str:
    return f"{label}：{value}"


def split_random_groups(
    runners: Sequence[int],
    *,
    group_count: int,
    group_size: int,
    rng: random.Random,
) -> tuple[tuple[int, ...], ...]:
    total = group_count * group_size
    if len(runners) != total:
        raise ValueError(f"expected {total} runners, got {len(runners)}")
    shuffled = list(runners)
    rng.shuffle(shuffled)
    return tuple(
        tuple(shuffled[index : index + group_size])
        for index in range(0, total, group_size)
    )


def simulate_stage(
    *,
    season: int,
    match_type: str,
    runners: Sequence[int],
    rng: random.Random,
    build_race_config_fn: BuildRaceConfigFn,
    simulate_race_fn: SimulateRaceFn,
    start_spec: str | None = None,
    track_length: int | None = None,
    initial_order: str | None = None,
    title: str | None = None,
) -> StageResult:
    rule = get_match_type_rule(season, match_type)
    resolved_start_spec = start_spec or resolve_match_start_spec(rule, runners)
    config = build_race_config_fn(
        season=season,
        runners=runners,
        start_spec=resolved_start_spec,
        track_length=track_length,
        initial_order=initial_order,
        qualify_cutoff=effective_qualify_cutoff(rule, len(runners)),
        match_rule=rule,
        name=title or rule.label,
    )
    result = simulate_race_fn(config, rng)
    ranking = tuple(result.ranking)
    next_stage_start_spec = build_group_round_two_start_spec(ranking) if rule.emits_seed_layout else None
    return StageResult(
        title=title or rule.label,
        match_type=rule.key,
        match_label=rule.label,
        entrants=config.runners,
        start_spec=resolved_start_spec,
        ranking=ranking,
        qualified_runners=qualified_runners_for_rule(rule, ranking),
        eliminated_runners=eliminated_runners_for_rule(rule, ranking),
        next_stage_start_spec=next_stage_start_spec,
        show_qualify_stats=rule.show_qualify_stats,
    )


def validate_champion_prediction_season(season: int) -> None:
    if season != 2:
        raise ValueError("--champion-prediction currently only supports --season 2")


def simulate_tournament(
    season: int,
    rng: random.Random,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    simulate_stage_fn: Callable[..., StageResult],
) -> TournamentResult:
    validate_champion_prediction_season(season)
    roster = season_runner_pool_fn(season)
    stages: list[StageResult] = []
    group_stage_groups = split_random_groups(roster, group_count=3, group_size=6, rng=rng)
    group_round_two_qualifiers: list[int] = []
    for label, entrants in zip(("A", "B", "C"), group_stage_groups, strict=True):
        round_one = simulate_stage_fn(
            season=season,
            match_type="group-round-1",
            runners=entrants,
            rng=rng,
            title=f"小组赛第一轮 {label}组",
        )
        stages.append(round_one)
        round_two = simulate_stage_fn(
            season=season,
            match_type="group-round-2",
            runners=round_one.ranking,
            rng=rng,
            title=f"小组赛第二轮 {label}组",
        )
        stages.append(round_two)
        group_round_two_qualifiers.extend(round_two.qualified_runners)

    elimination_groups = split_random_groups(group_round_two_qualifiers, group_count=2, group_size=6, rng=rng)
    winners_round_two_entrants: list[int] = []
    losers_round_one_entrants: list[int] = []
    for label, entrants in zip(("A", "B"), elimination_groups, strict=True):
        elimination = simulate_stage_fn(
            season=season,
            match_type="elimination",
            runners=entrants,
            rng=rng,
            title=f"淘汰赛 {label}组",
        )
        stages.append(elimination)
        winners_round_two_entrants.extend(elimination.qualified_runners)
        losers_round_one_entrants.extend(elimination.eliminated_runners)

    losers_round_one = simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=tuple(losers_round_one_entrants),
        rng=rng,
        title="败者组第一轮",
    )
    stages.append(losers_round_one)

    winners_round_two = simulate_stage_fn(
        season=season,
        match_type="winners-bracket",
        runners=tuple(winners_round_two_entrants),
        rng=rng,
        title="胜者组第二轮",
    )
    stages.append(winners_round_two)

    losers_round_two = simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=tuple(winners_round_two.eliminated_runners + losers_round_one.qualified_runners),
        rng=rng,
        title="败者组第二轮",
    )
    stages.append(losers_round_two)

    grand_final = simulate_stage_fn(
        season=season,
        match_type="grand-final",
        runners=tuple(winners_round_two.qualified_runners + losers_round_two.qualified_runners),
        rng=rng,
        title="总决赛",
    )
    stages.append(grand_final)
    return TournamentResult(
        season=season,
        stages=tuple(stages),
        champion=grand_final.ranking[0],
    )


def _group_round_one_title(group_label: str) -> str:
    return f"小组赛第一轮 {group_label}组"


def _group_round_two_title(group_label: str) -> str:
    return f"小组赛第二轮 {group_label}组"


def _elimination_title(group_label: str) -> str:
    return f"淘汰赛 {group_label}组"


def _simulate_group_round_one_and_two(
    *,
    season: int,
    group_label: str,
    round_one_entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> tuple[StageResult, StageResult]:
    round_one = simulate_stage_fn(
        season=season,
        match_type="group-round-1",
        runners=round_one_entrants,
        rng=rng,
        title=_group_round_one_title(group_label),
    )
    round_two = simulate_stage_fn(
        season=season,
        match_type="group-round-2",
        runners=round_one.ranking,
        rng=rng,
        title=_group_round_two_title(group_label),
    )
    return round_one, round_two


def _simulate_group_round_two_only(
    *,
    season: int,
    group_label: str,
    ranking_order_entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="group-round-2",
        runners=ranking_order_entrants,
        rng=rng,
        title=_group_round_two_title(group_label),
    )


def _simulate_elimination_stage(
    *,
    season: int,
    group_label: str,
    entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="elimination",
        runners=entrants,
        rng=rng,
        title=_elimination_title(group_label),
    )


def _simulate_losers_round_one(
    *,
    season: int,
    entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=entrants,
        rng=rng,
        title="败者组第一轮",
    )


def _simulate_winners_round_two(
    *,
    season: int,
    entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="winners-bracket",
        runners=entrants,
        rng=rng,
        title="胜者组第二轮",
    )


def _simulate_losers_round_two(
    *,
    season: int,
    entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="losers-bracket",
        runners=entrants,
        rng=rng,
        title="败者组第二轮",
    )


def _simulate_grand_final(
    *,
    season: int,
    entrants: Sequence[int],
    rng: random.Random,
    simulate_stage_fn: Callable[..., StageResult],
) -> StageResult:
    return simulate_stage_fn(
        season=season,
        match_type="grand-final",
        runners=entrants,
        rng=rng,
        title="总决赛",
    )


def _input_runners(
    request: TournamentEntryRequest,
    key: str,
) -> tuple[int, ...]:
    value = request.inputs.get(key)
    if value is None:
        raise ValueError(f"missing tournament input: {key}")
    if value and isinstance(value[0], tuple):  # type: ignore[index]
        raise ValueError(f"tournament input {key} must be a flat runner list")
    return tuple(value)  # type: ignore[arg-type]


def _input_grouped_runners(
    request: TournamentEntryRequest,
    key: str,
) -> tuple[tuple[int, ...], ...] | None:
    value = request.inputs.get(key)
    if value is None:
        return None
    if value and not isinstance(value[0], tuple):  # type: ignore[index]
        raise ValueError(f"tournament input {key} must be grouped")
    return tuple(tuple(group) for group in value)  # type: ignore[arg-type]


def simulate_tournament_from_entry_request(
    request: TournamentEntryRequest,
    rng: random.Random,
    *,
    simulate_stage_fn: Callable[..., StageResult],
) -> TournamentResult:
    validate_champion_prediction_season(request.season)
    entry = get_tournament_entry_point_definition(request.season, request.entry_point)
    remaining_stage_labels = tournament_entry_remaining_stage_labels(request.season, request.entry_point)
    input_context = tournament_entry_input_context(request)
    group_entry_keys = {
        "group-a-round-1",
        "group-a-round-2",
        "group-b-round-1",
        "group-b-round-2",
        "group-c-round-1",
        "group-c-round-2",
    }
    pre_losers_round_one_keys = group_entry_keys | {"elimination-a", "elimination-b", "losers-round-1"}
    pre_winners_round_two_keys = pre_losers_round_one_keys | {"winners-round-2"}
    stages: list[StageResult] = []
    qualifiers_a: tuple[int, ...] = ()
    qualifiers_b: tuple[int, ...] = ()
    qualifiers_c: tuple[int, ...] = ()
    winners_round_two_entrants: tuple[int, ...] = ()
    losers_round_one_entrants: tuple[int, ...] = ()
    winners_round_two_qualified: tuple[int, ...] = ()

    if entry.key == "group-a-round-1":
        roster = _input_runners(request, "season-roster")
        group_stage_groups = _input_grouped_runners(request, "group-stage-groups")
        if group_stage_groups is None:
            group_stage_groups = split_random_groups(roster, group_count=3, group_size=6, rng=rng)
        for label, entrants in zip(("A", "B", "C"), group_stage_groups, strict=True):
            round_one, round_two = _simulate_group_round_one_and_two(
                season=request.season,
                group_label=label,
                round_one_entrants=entrants,
                rng=rng,
                simulate_stage_fn=simulate_stage_fn,
            )
            stages.extend((round_one, round_two))
            if label == "A":
                qualifiers_a = round_two.qualified_runners
            elif label == "B":
                qualifiers_b = round_two.qualified_runners
            else:
                qualifiers_c = round_two.qualified_runners
    elif entry.key == "group-a-round-2":
        round_two = _simulate_group_round_two_only(
            season=request.season,
            group_label="A",
            ranking_order_entrants=_input_runners(request, "group-a-round-2-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(round_two)
        qualifiers_a = round_two.qualified_runners
        for label, key in (("B", "group-b-round-1-entrants"), ("C", "group-c-round-1-entrants")):
            round_one, next_round_two = _simulate_group_round_one_and_two(
                season=request.season,
                group_label=label,
                round_one_entrants=_input_runners(request, key),
                rng=rng,
                simulate_stage_fn=simulate_stage_fn,
            )
            stages.extend((round_one, next_round_two))
            if label == "B":
                qualifiers_b = next_round_two.qualified_runners
            else:
                qualifiers_c = next_round_two.qualified_runners
    elif entry.key == "group-b-round-1":
        qualifiers_a = _input_runners(request, "group-a-round-2-qualified")
        for label, key in (("B", "group-b-round-1-entrants"), ("C", "group-c-round-1-entrants")):
            round_one, round_two = _simulate_group_round_one_and_two(
                season=request.season,
                group_label=label,
                round_one_entrants=_input_runners(request, key),
                rng=rng,
                simulate_stage_fn=simulate_stage_fn,
            )
            stages.extend((round_one, round_two))
            if label == "B":
                qualifiers_b = round_two.qualified_runners
            else:
                qualifiers_c = round_two.qualified_runners
    elif entry.key == "group-b-round-2":
        qualifiers_a = _input_runners(request, "group-a-round-2-qualified")
        round_two = _simulate_group_round_two_only(
            season=request.season,
            group_label="B",
            ranking_order_entrants=_input_runners(request, "group-b-round-2-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(round_two)
        qualifiers_b = round_two.qualified_runners
        round_one, next_round_two = _simulate_group_round_one_and_two(
            season=request.season,
            group_label="C",
            round_one_entrants=_input_runners(request, "group-c-round-1-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.extend((round_one, next_round_two))
        qualifiers_c = next_round_two.qualified_runners
    elif entry.key == "group-c-round-1":
        qualifiers_a = _input_runners(request, "group-a-round-2-qualified")
        qualifiers_b = _input_runners(request, "group-b-round-2-qualified")
        round_one, round_two = _simulate_group_round_one_and_two(
            season=request.season,
            group_label="C",
            round_one_entrants=_input_runners(request, "group-c-round-1-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.extend((round_one, round_two))
        qualifiers_c = round_two.qualified_runners
    elif entry.key == "group-c-round-2":
        qualifiers_a = _input_runners(request, "group-a-round-2-qualified")
        qualifiers_b = _input_runners(request, "group-b-round-2-qualified")
        round_two = _simulate_group_round_two_only(
            season=request.season,
            group_label="C",
            ranking_order_entrants=_input_runners(request, "group-c-round-2-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(round_two)
        qualifiers_c = round_two.qualified_runners
    elif entry.key == "elimination-a":
        elimination_a = _simulate_elimination_stage(
            season=request.season,
            group_label="A",
            entrants=_input_runners(request, "elimination-a-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        elimination_b = _simulate_elimination_stage(
            season=request.season,
            group_label="B",
            entrants=_input_runners(request, "elimination-b-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.extend((elimination_a, elimination_b))
        winners_round_two_entrants = tuple(elimination_a.qualified_runners + elimination_b.qualified_runners)
        losers_round_one_entrants = tuple(elimination_a.eliminated_runners + elimination_b.eliminated_runners)
    elif entry.key == "elimination-b":
        elimination_a_ranking = _input_runners(request, "elimination-a-ranking")
        winners_round_two_entrants = tuple(elimination_a_ranking[:3])
        losers_round_one_entrants = tuple(elimination_a_ranking[3:])
        elimination_b = _simulate_elimination_stage(
            season=request.season,
            group_label="B",
            entrants=_input_runners(request, "elimination-b-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(elimination_b)
        winners_round_two_entrants = tuple(winners_round_two_entrants + elimination_b.qualified_runners)
        losers_round_one_entrants = tuple(losers_round_one_entrants + elimination_b.eliminated_runners)
    elif entry.key == "losers-round-1":
        losers_round_one_entrants = _input_runners(request, "losers-round-1-entrants")
        winners_round_two_entrants = _input_runners(request, "winners-round-2-entrants")
    elif entry.key == "winners-round-2":
        losers_round_one = None
        winners_round_two_entrants = _input_runners(request, "winners-round-2-entrants")
        losers_round_one_qualified = _input_runners(request, "losers-round-1-qualified")
    elif entry.key == "losers-round-2":
        winners_round_two_qualified = _input_runners(request, "winners-round-2-qualified")
        losers_round_two = _simulate_losers_round_two(
            season=request.season,
            entrants=_input_runners(request, "losers-round-2-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(losers_round_two)
        grand_final = _simulate_grand_final(
            season=request.season,
            entrants=tuple(winners_round_two_qualified + losers_round_two.qualified_runners),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(grand_final)
        return TournamentResult(
            season=request.season,
            stages=tuple(stages),
            champion=grand_final.ranking[0],
            start_entry_point=entry.key,
            start_entry_label=entry.label,
            remaining_stage_labels=remaining_stage_labels,
            input_context=input_context,
        )
    elif entry.key == "grand-final":
        grand_final = _simulate_grand_final(
            season=request.season,
            entrants=_input_runners(request, "grand-final-entrants"),
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(grand_final)
        return TournamentResult(
            season=request.season,
            stages=tuple(stages),
            champion=grand_final.ranking[0],
            start_entry_point=entry.key,
            start_entry_label=entry.label,
            remaining_stage_labels=remaining_stage_labels,
            input_context=input_context,
        )
    else:
        raise ValueError(f"unsupported tournament entry point: {entry.key}")

    if entry.key in group_entry_keys:
        elimination_groups = split_random_groups(
            tuple(qualifiers_a + qualifiers_b + qualifiers_c),
            group_count=2,
            group_size=6,
            rng=rng,
        )
        elimination_a = _simulate_elimination_stage(
            season=request.season,
            group_label="A",
            entrants=elimination_groups[0],
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        elimination_b = _simulate_elimination_stage(
            season=request.season,
            group_label="B",
            entrants=elimination_groups[1],
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.extend((elimination_a, elimination_b))
        winners_round_two_entrants = tuple(elimination_a.qualified_runners + elimination_b.qualified_runners)
        losers_round_one_entrants = tuple(elimination_a.eliminated_runners + elimination_b.eliminated_runners)

    if entry.key in pre_losers_round_one_keys:
        losers_round_one = _simulate_losers_round_one(
            season=request.season,
            entrants=losers_round_one_entrants,
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(losers_round_one)
        losers_round_one_qualified = losers_round_one.qualified_runners
    else:
        losers_round_one_qualified = _input_runners(request, "losers-round-1-qualified") if entry.key == "winners-round-2" else ()

    if entry.key in pre_winners_round_two_keys:
        winners_round_two = _simulate_winners_round_two(
            season=request.season,
            entrants=winners_round_two_entrants,
            rng=rng,
            simulate_stage_fn=simulate_stage_fn,
        )
        stages.append(winners_round_two)
        winners_round_two_qualified = winners_round_two.qualified_runners
        losers_round_two_entrants = tuple(winners_round_two.eliminated_runners + losers_round_one_qualified)
    else:
        losers_round_two_entrants = _input_runners(request, "losers-round-2-entrants")

    losers_round_two = _simulate_losers_round_two(
        season=request.season,
        entrants=losers_round_two_entrants,
        rng=rng,
        simulate_stage_fn=simulate_stage_fn,
    )
    stages.append(losers_round_two)
    grand_final = _simulate_grand_final(
        season=request.season,
        entrants=tuple(winners_round_two_qualified + losers_round_two.qualified_runners),
        rng=rng,
        simulate_stage_fn=simulate_stage_fn,
    )
    stages.append(grand_final)
    return TournamentResult(
        season=request.season,
        stages=tuple(stages),
        champion=grand_final.ranking[0],
        start_entry_point=entry.key,
        start_entry_label=entry.label,
        remaining_stage_labels=remaining_stage_labels,
        input_context=input_context,
    )


def simulate_tournament_chunk(
    season: int,
    iterations: int,
    seed: int | None,
    *,
    season_runner_pool_fn: SeasonRunnerPoolFn,
    simulate_tournament_fn: Callable[[int, random.Random], TournamentResult],
    derive_seed_fn: DeriveSeedFn,
    progress_batch_size_fn: ProgressBatchSizeFn,
    start_index: int = 0,
    progress: Any | None = None,
) -> ChampionPredictionAccumulator:
    acc = ChampionPredictionAccumulator(season_runner_pool_fn(season))
    chunk_rng = random.Random(seed)
    progress_batch = progress_batch_size_fn(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            tournament_rng = chunk_rng
        else:
            tournament_rng = random.Random(derive_seed_fn(seed, start_index + index))
        acc.add(simulate_tournament_fn(season, tournament_rng).champion)
        pending_progress += 1
        if progress is not None and (pending_progress >= progress_batch or index == iterations - 1):
            progress.advance(pending_progress)
            pending_progress = 0
    return acc


def tournament_entry_request_roster(request: TournamentEntryRequest) -> tuple[int, ...]:
    definition = get_tournament_entry_point_definition(request.season, request.entry_point)
    roster: list[int] = []
    seen: set[int] = set()
    for requirement in definition.requirements:
        value = request.inputs.get(requirement.key)
        if value is None:
            continue
        if requirement.kind == "grouped-entrants":
            flat_runners = [runner for group in value for runner in group]  # type: ignore[misc]
        else:
            flat_runners = list(value)  # type: ignore[arg-type]
        for runner in flat_runners:
            if runner not in seen:
                seen.add(runner)
                roster.append(runner)
    return tuple(roster)


def simulate_tournament_from_entry_request_chunk(
    request: TournamentEntryRequest,
    iterations: int,
    seed: int | None,
    *,
    simulate_tournament_from_entry_request_fn: Callable[[TournamentEntryRequest, random.Random], TournamentResult],
    derive_seed_fn: DeriveSeedFn,
    progress_batch_size_fn: ProgressBatchSizeFn,
    start_index: int = 0,
    progress: Any | None = None,
) -> ChampionPredictionAccumulator:
    acc = ChampionPredictionAccumulator(tournament_entry_request_roster(request))
    chunk_rng = random.Random(seed)
    progress_batch = progress_batch_size_fn(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            tournament_rng = chunk_rng
        else:
            tournament_rng = random.Random(derive_seed_fn(seed, start_index + index))
        acc.add(simulate_tournament_from_entry_request_fn(request, tournament_rng).champion)
        pending_progress += 1
        if progress is not None and (pending_progress >= progress_batch or index == iterations - 1):
            progress.advance(pending_progress)
            pending_progress = 0
    return acc


def stage_result_to_dict(result: StageResult) -> dict[str, object]:
    data: dict[str, object] = {
        "title": result.title,
        "match_type": result.match_type,
        "match_label": result.match_label,
        "entrants": list(result.entrants),
        "start_spec": result.start_spec,
        "ranking": list(result.ranking),
    }
    if result.show_qualify_stats:
        data["qualified_runners"] = list(result.qualified_runners)
        data["eliminated_runners"] = list(result.eliminated_runners)
    if result.next_stage_start_spec is not None:
        data["next_stage_start_spec"] = result.next_stage_start_spec
    return data


def tournament_input_snapshot_to_dict(snapshot: TournamentInputSnapshot) -> dict[str, object]:
    data: dict[str, object] = {
        "key": snapshot.key,
        "label": snapshot.label,
        "kind": snapshot.kind,
        "ordered": snapshot.ordered,
    }
    if snapshot.groups:
        data["groups"] = [list(group) for group in snapshot.groups]
    else:
        data["runners"] = list(snapshot.runners)
    return data


def tournament_result_to_dict(result: TournamentResult) -> dict[str, object]:
    data = {
        "season": result.season,
        "champion": result.champion,
        "champion_name": format_runner(result.champion),
        "elapsed_seconds": result.elapsed_seconds,
        "stages": [stage_result_to_dict(stage) for stage in result.stages],
    }
    if result.start_entry_point is not None:
        data["start_entry_point"] = result.start_entry_point
        data["start_entry_label"] = result.start_entry_label
        data["remaining_stage_labels"] = list(result.remaining_stage_labels)
        data["input_context"] = [tournament_input_snapshot_to_dict(item) for item in result.input_context]
    return data


def champion_prediction_races_per_second(summary: ChampionPredictionSummary) -> float | None:
    if summary.elapsed_seconds is None or summary.elapsed_seconds <= 0:
        return None
    return summary.iterations / summary.elapsed_seconds


def champion_prediction_to_dict(summary: ChampionPredictionSummary) -> dict[str, object]:
    rows = sorted(summary.rows, key=lambda row: row.champion_rate, reverse=True)
    data = {
        "season": summary.season,
        "iterations": summary.iterations,
        "elapsed_seconds": summary.elapsed_seconds,
        "tournaments_per_second": champion_prediction_races_per_second(summary),
        "best": {
            "runner": summary.best.runner,
            "name": summary.best.name,
            "championships": summary.best.championships,
            "champion_rate": summary.best.champion_rate,
        },
        "rows": [
            {
                "runner": row.runner,
                "name": row.name,
                "championships": row.championships,
                "champion_rate": row.champion_rate,
            }
            for row in rows
        ],
    }
    if summary.start_entry_point is not None:
        data["start_entry_point"] = summary.start_entry_point
        data["start_entry_label"] = summary.start_entry_label
        data["remaining_stage_labels"] = list(summary.remaining_stage_labels)
        data["input_context"] = [tournament_input_snapshot_to_dict(item) for item in summary.input_context]
    return data


def format_tournament_input_snapshot(snapshot: TournamentInputSnapshot) -> str:
    if snapshot.groups:
        parts = [f"{chr(ord('A') + index)}组：{format_runner_list(group)}" for index, group in enumerate(snapshot.groups)]
        return " | ".join(parts)
    prefix = "按顺序" if snapshot.ordered else "角色"
    return f"{prefix}：{format_runner_list(snapshot.runners)}"


def format_tournament_result(result: TournamentResult) -> str:
    lines = [
        "赛季冠军预测（单届）",
        format_runtime_status_line("赛季", f"第{result.season}季"),
        format_runtime_status_line("冠军", format_runner(result.champion)),
        format_runtime_status_line("用时", format_elapsed(result.elapsed_seconds)),
    ]
    if result.start_entry_point is not None:
        lines.append(format_runtime_status_line("起始阶段", result.start_entry_label or result.start_entry_point))
        lines.append(format_runtime_status_line("剩余赛程", " -> ".join(result.remaining_stage_labels)))
        for snapshot in result.input_context:
            lines.append(format_runtime_status_line(snapshot.label, format_tournament_input_snapshot(snapshot)))
    for stage in result.stages:
        lines.extend(
            [
                "",
                stage.title,
                f"参赛：{format_runner_list(stage.entrants)}",
                f"起跑：{stage.start_spec}",
                f"排名：{format_runner_arrow_list(stage.ranking)}",
            ]
        )
        if stage.show_qualify_stats:
            lines.append(f"晋级：{format_runner_list(stage.qualified_runners)}")
            lines.append(f"淘汰：{format_runner_list(stage.eliminated_runners)}")
        if stage.next_stage_start_spec is not None:
            lines.append(f"下一轮站位：{stage.next_stage_start_spec}")
    return "\n".join(lines)


def format_champion_prediction_summary(summary: ChampionPredictionSummary) -> str:
    rows = sorted(summary.rows, key=lambda row: row.champion_rate, reverse=True)
    headers = ("角色", "夺冠率", "冠军次数")
    table_rows = [
        (
            row.name,
            f"{row.champion_rate:.2%}",
            f"{row.championships:,}",
        )
        for row in rows
    ]
    columns = [headers, *table_rows]
    widths = [max(display_width(row[idx]) for row in columns) for idx in range(len(headers))]
    aligns = ("left", "right", "right")
    lines = [
        "赛季冠军预测（统计）",
        format_runtime_status_line("赛季", f"第{summary.season}季"),
        format_runtime_status_line("模拟届数", f"{summary.iterations:,}"),
        format_runtime_status_line("用时", format_elapsed(summary.elapsed_seconds)),
        format_runtime_status_line("速度", format_rate(champion_prediction_races_per_second(summary))),
        "",
        format_table_row(headers, widths, aligns),
        format_table_separator(widths),
    ]
    if summary.start_entry_point is not None:
        lines[5:5] = [
            format_runtime_status_line("起始阶段", summary.start_entry_label or summary.start_entry_point),
            format_runtime_status_line("剩余赛程", " -> ".join(summary.remaining_stage_labels)),
            *[
                format_runtime_status_line(snapshot.label, format_tournament_input_snapshot(snapshot))
                for snapshot in summary.input_context
            ],
        ]
    lines.extend(format_table_row(row, widths, aligns) for row in table_rows)
    lines.extend(
        [
            "",
            f"推荐选择：{summary.best.name}，夺冠概率 {summary.best.champion_rate:.2%}。",
        ]
    )
    return "\n".join(lines)
