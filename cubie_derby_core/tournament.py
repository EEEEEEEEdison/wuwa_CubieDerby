from __future__ import annotations

import math
import random
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from cubie_derby_core.match_types import (
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
class ChampionRouteTotals:
    winners_direct: int
    losers_comeback: int
    unknown: int


@dataclass(frozen=True)
class ChampionRouteAnalysisRow:
    runner: int
    name: str
    championships: int
    winners_direct: int
    losers_comeback: int
    unknown: int
    winners_direct_rate: float
    losers_comeback_rate: float
    unknown_rate: float


@dataclass(frozen=True)
class ChampionGrandFinalAnalysisRow:
    runner: int
    name: str
    appearances: int
    appearance_rate: float
    championships: int
    conversion_rate: float | None


@dataclass(frozen=True)
class ChampionStageAnalysisRow:
    stage_key: str
    stage_label: str
    runner: int
    name: str
    appearances: int
    appearance_rate: float
    stage_wins: int
    stage_win_rate: float | None
    qualified: int
    qualify_rate: float | None
    eliminated: int
    elimination_rate: float | None
    average_rank: float | None


@dataclass(frozen=True)
class ChampionMapAnalysisRow:
    map_key: str
    map_label: str
    runner: int
    name: str
    appearances: int
    appearances_per_tournament: float
    stage_wins: int
    stage_win_rate: float | None
    qualified: int
    qualify_rate: float | None
    average_rank: float | None


@dataclass(frozen=True)
class ChampionAdvancedAnalysis:
    route_totals: ChampionRouteTotals
    route_rows: tuple[ChampionRouteAnalysisRow, ...]
    grand_final_rows: tuple[ChampionGrandFinalAnalysisRow, ...]
    stage_rows: tuple[ChampionStageAnalysisRow, ...]
    map_rows: tuple[ChampionMapAnalysisRow, ...]


@dataclass(frozen=True)
class ChampionPredictionSummary:
    season: int
    iterations: int
    rows: tuple[ChampionPredictionRow, ...]
    elapsed_seconds: float | None = None
    analysis_depth: str = "fast"
    advanced: ChampionAdvancedAnalysis | None = None
    start_entry_point: str | None = None
    start_entry_label: str | None = None
    remaining_stage_labels: tuple[str, ...] = ()
    input_context: tuple[TournamentInputSnapshot, ...] = ()

    @property
    def best(self) -> ChampionPredictionRow:
        return max(self.rows, key=lambda row: row.champion_rate)


class ChampionPredictionAccumulator:
    def __init__(self, roster: Sequence[int], analysis_depth: str = "fast") -> None:
        if analysis_depth not in {"fast", "advanced"}:
            raise ValueError(f"unknown champion analysis depth: {analysis_depth}")
        self.roster = tuple(roster)
        self.index = {runner: i for i, runner in enumerate(self.roster)}
        self.iterations = 0
        self.championships = [0] * len(self.roster)
        self.analysis_depth = analysis_depth
        self._advanced_enabled = analysis_depth == "advanced"
        if self._advanced_enabled:
            size = len(self.roster)
            stage_count = len(CHAMPION_ANALYSIS_STAGE_DEFINITIONS)
            map_count = len(CHAMPION_ANALYSIS_MAP_DEFINITIONS)
            self.route_winners_direct = [0] * size
            self.route_losers_comeback = [0] * size
            self.route_unknown = [0] * size
            self.grand_final_appearances = [0] * size
            self.stage_appearances = [[0] * size for _ in range(stage_count)]
            self.stage_wins = [[0] * size for _ in range(stage_count)]
            self.stage_qualified = [[0] * size for _ in range(stage_count)]
            self.stage_eliminated = [[0] * size for _ in range(stage_count)]
            self.stage_qualify_opportunities = [[0] * size for _ in range(stage_count)]
            self.stage_rank_sum = [[0] * size for _ in range(stage_count)]
            self.map_appearances = [[0] * size for _ in range(map_count)]
            self.map_wins = [[0] * size for _ in range(map_count)]
            self.map_qualified = [[0] * size for _ in range(map_count)]
            self.map_qualify_opportunities = [[0] * size for _ in range(map_count)]
            self.map_rank_sum = [[0] * size for _ in range(map_count)]

    def add(self, champion: int) -> None:
        self.iterations += 1
        self.championships[self.index[champion]] += 1

    def add_tournament(self, result: TournamentResult) -> None:
        self.add(result.champion)
        if self._advanced_enabled:
            self._add_advanced_result(result)

    def _add_advanced_result(self, result: TournamentResult) -> None:
        champion_idx = self.index[result.champion]
        route = champion_route_key(result)
        if route == "winners-direct":
            self.route_winners_direct[champion_idx] += 1
        elif route == "losers-comeback":
            self.route_losers_comeback[champion_idx] += 1
        else:
            self.route_unknown[champion_idx] += 1

        for stage in result.stages:
            stage_key = champion_stage_analysis_key(stage)
            stage_idx = CHAMPION_ANALYSIS_STAGE_INDEX[stage_key]
            map_key = champion_stage_map_key(stage)
            map_idx = CHAMPION_ANALYSIS_MAP_INDEX[map_key]

            if stage.ranking:
                winner_idx = self.index[stage.ranking[0]]
                self.stage_wins[stage_idx][winner_idx] += 1
                self.map_wins[map_idx][winner_idx] += 1

            for rank, runner in enumerate(stage.ranking, start=1):
                runner_idx = self.index[runner]
                self.stage_appearances[stage_idx][runner_idx] += 1
                self.stage_rank_sum[stage_idx][runner_idx] += rank
                self.map_appearances[map_idx][runner_idx] += 1
                self.map_rank_sum[map_idx][runner_idx] += rank

            if stage.show_qualify_stats:
                for runner in stage.entrants:
                    runner_idx = self.index[runner]
                    self.stage_qualify_opportunities[stage_idx][runner_idx] += 1
                    self.map_qualify_opportunities[map_idx][runner_idx] += 1
                for runner in stage.qualified_runners:
                    runner_idx = self.index[runner]
                    self.stage_qualified[stage_idx][runner_idx] += 1
                    self.map_qualified[map_idx][runner_idx] += 1
                for runner in stage.eliminated_runners:
                    self.stage_eliminated[stage_idx][self.index[runner]] += 1

            if stage_key == "grand-final":
                for runner in stage.entrants:
                    self.grand_final_appearances[self.index[runner]] += 1

    def merge(self, other: "ChampionPredictionAccumulator") -> None:
        if self.roster != other.roster:
            raise ValueError("cannot merge champion accumulators for different rosters")
        if self.analysis_depth != other.analysis_depth:
            raise ValueError("cannot merge champion accumulators with different analysis depths")
        self.iterations += other.iterations
        for index in range(len(self.roster)):
            self.championships[index] += other.championships[index]
        if self._advanced_enabled:
            _merge_counter_lists(self.route_winners_direct, other.route_winners_direct)
            _merge_counter_lists(self.route_losers_comeback, other.route_losers_comeback)
            _merge_counter_lists(self.route_unknown, other.route_unknown)
            _merge_counter_lists(self.grand_final_appearances, other.grand_final_appearances)
            _merge_counter_matrices(self.stage_appearances, other.stage_appearances)
            _merge_counter_matrices(self.stage_wins, other.stage_wins)
            _merge_counter_matrices(self.stage_qualified, other.stage_qualified)
            _merge_counter_matrices(self.stage_eliminated, other.stage_eliminated)
            _merge_counter_matrices(self.stage_qualify_opportunities, other.stage_qualify_opportunities)
            _merge_counter_matrices(self.stage_rank_sum, other.stage_rank_sum)
            _merge_counter_matrices(self.map_appearances, other.map_appearances)
            _merge_counter_matrices(self.map_wins, other.map_wins)
            _merge_counter_matrices(self.map_qualified, other.map_qualified)
            _merge_counter_matrices(self.map_qualify_opportunities, other.map_qualify_opportunities)
            _merge_counter_matrices(self.map_rank_sum, other.map_rank_sum)

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
            analysis_depth=self.analysis_depth,
            advanced=self._build_advanced_analysis() if self._advanced_enabled else None,
            start_entry_point=start_entry_point,
            start_entry_label=start_entry_label,
            remaining_stage_labels=remaining_stage_labels,
            input_context=input_context,
        )

    def _build_advanced_analysis(self) -> ChampionAdvancedAnalysis:
        total = self.iterations
        route_rows: list[ChampionRouteAnalysisRow] = []
        grand_final_rows: list[ChampionGrandFinalAnalysisRow] = []
        stage_rows: list[ChampionStageAnalysisRow] = []
        map_rows: list[ChampionMapAnalysisRow] = []

        for runner in self.roster:
            idx = self.index[runner]
            championships = self.championships[idx]
            winners_direct = self.route_winners_direct[idx]
            losers_comeback = self.route_losers_comeback[idx]
            unknown = self.route_unknown[idx]
            route_rows.append(
                ChampionRouteAnalysisRow(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    championships=championships,
                    winners_direct=winners_direct,
                    losers_comeback=losers_comeback,
                    unknown=unknown,
                    winners_direct_rate=winners_direct / championships if championships else 0.0,
                    losers_comeback_rate=losers_comeback / championships if championships else 0.0,
                    unknown_rate=unknown / championships if championships else 0.0,
                )
            )

            final_appearances = self.grand_final_appearances[idx]
            grand_final_rows.append(
                ChampionGrandFinalAnalysisRow(
                    runner=runner,
                    name=RUNNER_NAMES.get(runner, str(runner)),
                    appearances=final_appearances,
                    appearance_rate=final_appearances / total if total else math.nan,
                    championships=championships,
                    conversion_rate=championships / final_appearances if final_appearances else None,
                )
            )

        for stage_idx, (stage_key, stage_label) in enumerate(CHAMPION_ANALYSIS_STAGE_DEFINITIONS):
            for runner in self.roster:
                idx = self.index[runner]
                appearances = self.stage_appearances[stage_idx][idx]
                qualify_opportunities = self.stage_qualify_opportunities[stage_idx][idx]
                stage_rows.append(
                    ChampionStageAnalysisRow(
                        stage_key=stage_key,
                        stage_label=stage_label,
                        runner=runner,
                        name=RUNNER_NAMES.get(runner, str(runner)),
                        appearances=appearances,
                        appearance_rate=appearances / total if total else math.nan,
                        stage_wins=self.stage_wins[stage_idx][idx],
                        stage_win_rate=self.stage_wins[stage_idx][idx] / appearances if appearances else None,
                        qualified=self.stage_qualified[stage_idx][idx],
                        qualify_rate=(
                            self.stage_qualified[stage_idx][idx] / qualify_opportunities
                            if qualify_opportunities
                            else None
                        ),
                        eliminated=self.stage_eliminated[stage_idx][idx],
                        elimination_rate=(
                            self.stage_eliminated[stage_idx][idx] / qualify_opportunities
                            if qualify_opportunities
                            else None
                        ),
                        average_rank=self.stage_rank_sum[stage_idx][idx] / appearances if appearances else None,
                    )
                )

        for map_idx, (map_key, map_label) in enumerate(CHAMPION_ANALYSIS_MAP_DEFINITIONS):
            for runner in self.roster:
                idx = self.index[runner]
                appearances = self.map_appearances[map_idx][idx]
                qualify_opportunities = self.map_qualify_opportunities[map_idx][idx]
                map_rows.append(
                    ChampionMapAnalysisRow(
                        map_key=map_key,
                        map_label=map_label,
                        runner=runner,
                        name=RUNNER_NAMES.get(runner, str(runner)),
                        appearances=appearances,
                        appearances_per_tournament=appearances / total if total else math.nan,
                        stage_wins=self.map_wins[map_idx][idx],
                        stage_win_rate=self.map_wins[map_idx][idx] / appearances if appearances else None,
                        qualified=self.map_qualified[map_idx][idx],
                        qualify_rate=(
                            self.map_qualified[map_idx][idx] / qualify_opportunities
                            if qualify_opportunities
                            else None
                        ),
                        average_rank=self.map_rank_sum[map_idx][idx] / appearances if appearances else None,
                    )
                )

        return ChampionAdvancedAnalysis(
            route_totals=ChampionRouteTotals(
                winners_direct=sum(self.route_winners_direct),
                losers_comeback=sum(self.route_losers_comeback),
                unknown=sum(self.route_unknown),
            ),
            route_rows=tuple(route_rows),
            grand_final_rows=tuple(grand_final_rows),
            stage_rows=tuple(stage_rows),
            map_rows=tuple(map_rows),
        )


CHAMPION_ANALYSIS_STAGE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("group-round-1", "小组赛第一轮"),
    ("group-round-2", "小组赛第二轮"),
    ("elimination", "淘汰赛"),
    ("losers-round-1", "败者组第一轮"),
    ("winners-round-2", "胜者组"),
    ("losers-round-2", "败者组第二轮"),
    ("grand-final", "总决赛"),
)
CHAMPION_ANALYSIS_STAGE_INDEX = {
    key: index for index, (key, _label) in enumerate(CHAMPION_ANALYSIS_STAGE_DEFINITIONS)
}

CHAMPION_ANALYSIS_MAP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("group-stage", "小组赛阶段地图"),
    ("knockout-stage", "淘汰赛阶段地图"),
)
CHAMPION_ANALYSIS_MAP_INDEX = {
    key: index for index, (key, _label) in enumerate(CHAMPION_ANALYSIS_MAP_DEFINITIONS)
}


def _merge_counter_lists(target: list[int], source: list[int]) -> None:
    for index in range(len(target)):
        target[index] += source[index]


def _merge_counter_matrices(target: list[list[int]], source: list[list[int]]) -> None:
    for row_index in range(len(target)):
        _merge_counter_lists(target[row_index], source[row_index])


def champion_stage_analysis_key(stage: StageResult) -> str:
    if stage.match_type in {"group-round-1", "group-round-2", "elimination", "grand-final"}:
        return stage.match_type
    if stage.match_type == "winners-bracket":
        return "winners-round-2"
    if stage.match_type == "losers-bracket":
        return "losers-round-1" if "第一轮" in stage.title else "losers-round-2"
    raise ValueError(f"unsupported tournament stage for advanced analysis: {stage.match_type}")


def champion_stage_map_key(stage: StageResult) -> str:
    return "group-stage" if stage.match_type in {"group-round-1", "group-round-2"} else "knockout-stage"


def champion_route_key(result: TournamentResult) -> str:
    champion = result.champion
    winners_direct: set[int] = set()
    losers_comeback: set[int] = set()
    for snapshot in result.input_context:
        if snapshot.key == "winners-round-2-qualified":
            winners_direct.update(snapshot.runners)
    for stage in result.stages:
        stage_key = champion_stage_analysis_key(stage)
        if stage_key == "winners-round-2":
            winners_direct.update(stage.qualified_runners)
        elif stage_key == "losers-round-2":
            losers_comeback.update(stage.qualified_runners)
    if champion in winners_direct:
        return "winners-direct"
    if champion in losers_comeback:
        return "losers-comeback"
    return "unknown"


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


def format_ranked_runner_list(runners: Sequence[int]) -> str:
    return "，".join(f"{index}. {format_runner(runner)}" for index, runner in enumerate(runners, start=1))


def _parse_start_spec_cells(start_spec: str) -> dict[int, tuple[str, ...]]:
    cells: dict[int, tuple[str, ...]] = {}
    for part in start_spec.split(";"):
        part = part.strip()
        if not part:
            continue
        pos_text, runners_text = part.split(":", 1)
        runners = tuple(token.strip() for token in runners_text.split(",") if token.strip())
        cells[int(pos_text)] = runners
    return cells


def _ranking_order_from_start_spec(start_spec: str) -> tuple[int, ...] | None:
    cells = _parse_start_spec_cells(start_spec)
    if set(cells) != {-3, -2, -1, 0}:
        return None
    if not (
        len(cells[0]) == 1
        and len(cells[-1]) == 2
        and len(cells[-2]) == 2
        and len(cells[-3]) == 1
    ):
        return None
    try:
        return (
            int(cells[0][0]),
            int(cells[-1][0]),
            int(cells[-1][1]),
            int(cells[-2][0]),
            int(cells[-2][1]),
            int(cells[-3][0]),
        )
    except ValueError:
        return None


def format_start_rule(start_spec: str) -> str:
    cells = _parse_start_spec_cells(start_spec)
    if any("*" in runners for runners in cells.values()):
        return "随机"
    ranking_order = _ranking_order_from_start_spec(start_spec)
    if ranking_order is not None:
        return f"排名顺序（{format_ranked_runner_list(ranking_order)}）"
    parts = [
        f"{pos}: {format_runner_list(tuple(int(runner) for runner in runners))}"
        for pos, runners in sorted(cells.items())
    ]
    return f"自定义（{' | '.join(parts)}）"


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
    analysis_depth: str = "fast",
    start_index: int = 0,
    progress: Any | None = None,
) -> ChampionPredictionAccumulator:
    acc = ChampionPredictionAccumulator(season_runner_pool_fn(season), analysis_depth=analysis_depth)
    chunk_rng = random.Random(seed)
    progress_batch = progress_batch_size_fn(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            tournament_rng = chunk_rng
        else:
            tournament_rng = random.Random(derive_seed_fn(seed, start_index + index))
        tournament = simulate_tournament_fn(season, tournament_rng)
        if analysis_depth == "advanced":
            acc.add_tournament(tournament)
        else:
            acc.add(tournament.champion)
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
    analysis_depth: str = "fast",
    start_index: int = 0,
    progress: Any | None = None,
) -> ChampionPredictionAccumulator:
    acc = ChampionPredictionAccumulator(tournament_entry_request_roster(request), analysis_depth=analysis_depth)
    chunk_rng = random.Random(seed)
    progress_batch = progress_batch_size_fn(iterations)
    pending_progress = 0
    for index in range(iterations):
        if seed is None:
            tournament_rng = chunk_rng
        else:
            tournament_rng = random.Random(derive_seed_fn(seed, start_index + index))
        tournament = simulate_tournament_from_entry_request_fn(request, tournament_rng)
        if analysis_depth == "advanced":
            acc.add_tournament(tournament)
        else:
            acc.add(tournament.champion)
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
        "analysis_depth": summary.analysis_depth,
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
    if summary.advanced is not None:
        data["advanced"] = champion_advanced_analysis_to_dict(summary.advanced)
    if summary.start_entry_point is not None:
        data["start_entry_point"] = summary.start_entry_point
        data["start_entry_label"] = summary.start_entry_label
        data["remaining_stage_labels"] = list(summary.remaining_stage_labels)
        data["input_context"] = [tournament_input_snapshot_to_dict(item) for item in summary.input_context]
    return data


def champion_advanced_analysis_to_dict(advanced: ChampionAdvancedAnalysis) -> dict[str, object]:
    return {
        "route_totals": {
            "winners_direct": advanced.route_totals.winners_direct,
            "losers_comeback": advanced.route_totals.losers_comeback,
            "unknown": advanced.route_totals.unknown,
        },
        "route_rows": [
            {
                "runner": row.runner,
                "name": row.name,
                "championships": row.championships,
                "winners_direct": row.winners_direct,
                "losers_comeback": row.losers_comeback,
                "unknown": row.unknown,
                "winners_direct_rate": row.winners_direct_rate,
                "losers_comeback_rate": row.losers_comeback_rate,
                "unknown_rate": row.unknown_rate,
            }
            for row in sorted(advanced.route_rows, key=lambda item: item.championships, reverse=True)
        ],
        "grand_final_rows": [
            {
                "runner": row.runner,
                "name": row.name,
                "appearances": row.appearances,
                "appearance_rate": row.appearance_rate,
                "championships": row.championships,
                "conversion_rate": row.conversion_rate,
            }
            for row in sorted(
                advanced.grand_final_rows,
                key=lambda item: (item.appearances, item.championships),
                reverse=True,
            )
        ],
        "stage_rows": [
            {
                "stage_key": row.stage_key,
                "stage_label": row.stage_label,
                "runner": row.runner,
                "name": row.name,
                "appearances": row.appearances,
                "appearance_rate": row.appearance_rate,
                "stage_wins": row.stage_wins,
                "stage_win_rate": row.stage_win_rate,
                "qualified": row.qualified,
                "qualify_rate": row.qualify_rate,
                "eliminated": row.eliminated,
                "elimination_rate": row.elimination_rate,
                "average_rank": row.average_rank,
            }
            for row in advanced.stage_rows
        ],
        "map_rows": [
            {
                "map_key": row.map_key,
                "map_label": row.map_label,
                "runner": row.runner,
                "name": row.name,
                "appearances": row.appearances,
                "appearances_per_tournament": row.appearances_per_tournament,
                "stage_wins": row.stage_wins,
                "stage_win_rate": row.stage_win_rate,
                "qualified": row.qualified,
                "qualify_rate": row.qualify_rate,
                "average_rank": row.average_rank,
            }
            for row in advanced.map_rows
        ],
    }


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
                f"起跑规则：{format_start_rule(stage.start_spec)}",
                f"排名：{format_ranked_runner_list(stage.ranking)}",
            ]
        )
        if stage.show_qualify_stats:
            lines.append(f"晋级：{format_runner_list(stage.qualified_runners)}")
            lines.append(f"淘汰：{format_runner_list(stage.eliminated_runners)}")
        if stage.next_stage_start_spec is not None:
            lines.append(f"下一轮起跑规则：{format_start_rule(stage.next_stage_start_spec)}")
    return "\n".join(lines)


def _format_optional_percent(value: float | None) -> str:
    return "未进入" if value is None else f"{value:.2%}"


def _format_optional_rank(value: float | None) -> str:
    return "未进入" if value is None else f"{value:.2f}"


def _format_analysis_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    aligns: Sequence[str],
) -> list[str]:
    columns = [headers, *rows]
    widths = [max(display_width(row[idx]) for row in columns) for idx in range(len(headers))]
    return [
        format_table_row(headers, widths, aligns),
        format_table_separator(widths),
        *[format_table_row(row, widths, aligns) for row in rows],
    ]


def _stage_row_lookup(advanced: ChampionAdvancedAnalysis) -> dict[tuple[int, str], ChampionStageAnalysisRow]:
    return {(row.runner, row.stage_key): row for row in advanced.stage_rows}


def _map_row_lookup(advanced: ChampionAdvancedAnalysis) -> dict[tuple[int, str], ChampionMapAnalysisRow]:
    return {(row.runner, row.map_key): row for row in advanced.map_rows}


def _format_champion_advanced_analysis(advanced: ChampionAdvancedAnalysis, iterations: int) -> list[str]:
    route_total = (
        advanced.route_totals.winners_direct
        + advanced.route_totals.losers_comeback
        + advanced.route_totals.unknown
    )
    route_lines = [
        "高阶分析",
        format_runtime_status_line(
            "冠军路线",
            (
                f"胜者组直通 {advanced.route_totals.winners_direct:,} "
                f"({advanced.route_totals.winners_direct / route_total:.2%})；"
                f"败者组复活 {advanced.route_totals.losers_comeback:,} "
                f"({advanced.route_totals.losers_comeback / route_total:.2%})；"
                f"未知 {advanced.route_totals.unknown:,} "
                f"({advanced.route_totals.unknown / route_total:.2%})"
            )
            if route_total
            else "暂无数据",
        ),
    ]

    final_rows = [
        (
            row.name,
            f"{row.appearance_rate:.2%}",
            _format_optional_percent(row.conversion_rate),
            f"{row.championships:,}",
        )
        for row in sorted(
            advanced.grand_final_rows,
            key=lambda item: (item.conversion_rate or -1.0, item.appearances),
            reverse=True,
        )
    ]

    stage_lookup = _stage_row_lookup(advanced)
    stage_columns = (
        ("group-round-1", "小组1"),
        ("group-round-2", "小组2"),
        ("elimination", "淘汰"),
        ("losers-round-1", "败者1"),
        ("winners-round-2", "胜者"),
        ("losers-round-2", "败者2"),
        ("grand-final", "决赛"),
    )
    runner_order = [row.runner for row in sorted(advanced.grand_final_rows, key=lambda item: item.appearances, reverse=True)]
    funnel_rows = []
    for runner in runner_order:
        name = RUNNER_NAMES.get(runner, str(runner))
        funnel_rows.append(
            (
                name,
                *[
                    f"{stage_lookup[(runner, stage_key)].appearance_rate:.0%}"
                    for stage_key, _label in stage_columns
                ],
            )
        )

    map_lookup = _map_row_lookup(advanced)
    map_rows = []
    for runner in runner_order:
        group_row = map_lookup[(runner, "group-stage")]
        knockout_row = map_lookup[(runner, "knockout-stage")]
        map_rows.append(
            (
                RUNNER_NAMES.get(runner, str(runner)),
                _format_optional_rank(group_row.average_rank),
                _format_optional_percent(group_row.stage_win_rate),
                _format_optional_rank(knockout_row.average_rank),
                _format_optional_percent(knockout_row.stage_win_rate),
            )
        )

    return [
        *route_lines,
        "",
        "总决赛转化率",
        *_format_analysis_table(
            ("角色", "进决赛率", "决赛夺冠率", "冠军次数"),
            final_rows,
            ("left", "right", "right", "right"),
        ),
        "",
        "阶段进入率",
        *_format_analysis_table(
            ("角色", *[label for _key, label in stage_columns]),
            funnel_rows,
            ("left", "right", "right", "right", "right", "right", "right", "right"),
        ),
        "",
        "地图表现",
        *_format_analysis_table(
            ("角色", "小组均名", "小组胜率", "淘汰均名", "淘汰胜率"),
            map_rows,
            ("left", "right", "right", "right", "right"),
        ),
    ]


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
    if summary.advanced is not None:
        lines.extend(["", *_format_champion_advanced_analysis(summary.advanced, summary.iterations)])
    return "\n".join(lines)
