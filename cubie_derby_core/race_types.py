"""Pure dataclass types used across the simulator.

These types have no behaviour beyond what `@dataclass` synthesises and
hold no module-level state. They were originally defined inline in
`cubie_derby.py`; moving them here is a structural refactor that lets
`cubie_derby.py` stay closer to a thin facade while keeping every name
available at the entry-script level for backwards compatibility.

Importers should normally pull these names through `cubie_derby` (which
re-exports them); core modules should import from this module directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RaceConfig:
    runners: tuple[int, ...]
    track_length: int
    start_grid: dict[int, tuple[int, ...]]
    qualify_cutoff: int = 4
    season: int = 1
    forward_cells: frozenset[int] = field(default_factory=frozenset)
    backward_cells: frozenset[int] = field(default_factory=frozenset)
    shuffle_cells: frozenset[int] = field(default_factory=frozenset)
    npc_enabled: bool = False
    npc_start_round: int = 3
    random_start_stack: bool = False
    random_start_position: int = 0
    initial_order_mode: str = "random"  # random, start, fixed
    fixed_initial_order: tuple[int, ...] = ()
    disabled_skills: frozenset[int] = field(default_factory=frozenset)
    match_type: str | None = None
    show_qualify_stats: bool = True
    map_label: str | None = None
    name: str = "自定义"


@dataclass(frozen=True)
class RaceResult:
    winner: int
    ranking: tuple[int, ...]
    second_position: int
    winner_margin: int
    winner_carried_steps: int = 0
    winner_total_steps: int = 0
    movement_stats: tuple[tuple[int, int, int], ...] = ()
    skill_success_counts: tuple[tuple[int, int], ...] = ()


@dataclass
class RaceSkillState:
    hiyuki_bonus_steps: int = 0
    denia_last_dice: int | None = None
    mornye_next_dice: int = 3
    aemeath_available: bool = True
    aemeath_ready: bool = False
    augusta_force_last_next_round: bool = False
    luno_available: bool = True
    success_counts: dict[int, int] = field(default_factory=dict)


@dataclass
class RaceMovementState:
    total_steps: dict[int, int] = field(default_factory=dict)
    carried_steps: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSuccessBucket:
    success_count: int
    races: int
    wins: int
    win_rate: float


@dataclass(frozen=True)
class RunnerSummary:
    runner: int
    name: str
    wins: int
    win_rate: float
    qualify_count: int
    qualify_rate: float
    average_rank: float
    rank_variance: float
    winner_gap_per_race: float
    average_winning_margin: float
    lazy_win_rate: float = 0.0
    winner_carried_steps: int = 0
    winner_total_steps: int = 0
    skill_average_success_count: float = 0.0
    skill_marginal_win_rate: float | None = None
    skill_success_distribution: tuple[SkillSuccessBucket, ...] = ()


@dataclass(frozen=True)
class SimulationSummary:
    iterations: int
    config: RaceConfig
    rows: tuple[RunnerSummary, ...]
    elapsed_seconds: float | None = None

    @property
    def best(self) -> RunnerSummary:
        return max(self.rows, key=lambda row: (row.win_rate, -row.average_rank))


@dataclass(frozen=True)
class SkillAblationRow:
    runner: int
    name: str
    enabled_win_rate: float
    disabled_win_rate: float
    net_win_rate: float
    skill_average_success_count: float
    skill_marginal_win_rate: float | None
    success_distribution: tuple[SkillSuccessBucket, ...]


@dataclass(frozen=True)
class SkillAblationSummary:
    iterations: int
    total_simulated_races: int
    base_summary: SimulationSummary
    rows: tuple[SkillAblationRow, ...]
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class SeasonRosterScanRow:
    runner: int
    name: str
    combination_count: int
    race_count: int
    wins: int
    win_rate: float
    qualify_count: int
    qualify_rate: float
    average_rank: float
    rank_variance: float
    winner_gap_per_race: float
    average_winning_margin: float
    lazy_win_rate: float = 0.0
    winner_carried_steps: int = 0
    winner_total_steps: int = 0


@dataclass(frozen=True)
class SeasonRosterScanSummary:
    season: int
    roster: tuple[int, ...]
    field_size: int
    qualify_cutoff: int
    iterations_per_combination: int
    combination_count: int
    total_simulated_races: int
    start_spec: str
    track_length: int
    initial_order_mode: str
    rows: tuple[SeasonRosterScanRow, ...]
    elapsed_seconds: float | None = None

    @property
    def best(self) -> SeasonRosterScanRow:
        return max(self.rows, key=lambda row: (row.win_rate, -row.average_rank))


__all__ = [
    "RaceConfig",
    "RaceResult",
    "RaceSkillState",
    "RaceMovementState",
    "SkillSuccessBucket",
    "RunnerSummary",
    "SimulationSummary",
    "SkillAblationRow",
    "SkillAblationSummary",
    "SeasonRosterScanRow",
    "SeasonRosterScanSummary",
]
