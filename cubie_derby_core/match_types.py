from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


ADVANCEMENT_ALL = "all"
ADVANCEMENT_TOP_N = "top_n"
ADVANCEMENT_NONE = "none"


@dataclass(frozen=True)
class MatchTypeRule:
    key: str
    label: str
    season: int
    default_start: str | None
    advancement_mode: str
    qualify_cutoff: int | None = None
    seeded_from_runner_order: bool = False
    emits_seed_layout: bool = False
    map_variant: str = "default"

    @property
    def show_qualify_stats(self) -> bool:
        return self.advancement_mode == ADVANCEMENT_TOP_N


SEASON2_MATCH_TYPES: dict[str, MatchTypeRule] = {
    "group-round-1": MatchTypeRule(
        key="group-round-1",
        label="小组赛第一轮",
        season=2,
        default_start="1:*",
        advancement_mode=ADVANCEMENT_ALL,
        emits_seed_layout=True,
        map_variant="group-stage",
    ),
    "group-round-2": MatchTypeRule(
        key="group-round-2",
        label="小组赛第二轮",
        season=2,
        default_start=None,
        advancement_mode=ADVANCEMENT_TOP_N,
        qualify_cutoff=4,
        seeded_from_runner_order=True,
        map_variant="group-stage",
    ),
    "elimination": MatchTypeRule(
        key="elimination",
        label="淘汰赛",
        season=2,
        default_start="1:*",
        advancement_mode=ADVANCEMENT_TOP_N,
        qualify_cutoff=3,
        map_variant="knockout-stage",
    ),
    "losers-bracket": MatchTypeRule(
        key="losers-bracket",
        label="败者组",
        season=2,
        default_start="1:*",
        advancement_mode=ADVANCEMENT_TOP_N,
        qualify_cutoff=3,
        map_variant="knockout-stage",
    ),
    "winners-bracket": MatchTypeRule(
        key="winners-bracket",
        label="胜者组",
        season=2,
        default_start="1:*",
        advancement_mode=ADVANCEMENT_TOP_N,
        qualify_cutoff=3,
        map_variant="knockout-stage",
    ),
    "grand-final": MatchTypeRule(
        key="grand-final",
        label="总决赛",
        season=2,
        default_start="1:*",
        advancement_mode=ADVANCEMENT_NONE,
        map_variant="knockout-stage",
    ),
}

MATCH_TYPE_ALIASES = {
    "group-round-1": "group-round-1",
    "group1": "group-round-1",
    "group-round1": "group-round-1",
    "group_round_1": "group-round-1",
    "小组赛第一轮": "group-round-1",
    "小组赛1": "group-round-1",
    "group-round-2": "group-round-2",
    "group2": "group-round-2",
    "group-round2": "group-round-2",
    "group_round_2": "group-round-2",
    "小组赛第二轮": "group-round-2",
    "小组赛2": "group-round-2",
    "elimination": "elimination",
    "knockout": "elimination",
    "淘汰赛": "elimination",
    "losers-bracket": "losers-bracket",
    "losers": "losers-bracket",
    "败者组": "losers-bracket",
    "winners-bracket": "winners-bracket",
    "winners": "winners-bracket",
    "胜者组": "winners-bracket",
    "grand-final": "grand-final",
    "final": "grand-final",
    "grandfinal": "grand-final",
    "总决赛": "grand-final",
}


def normalize_match_type(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("match type cannot be empty")
    alias = MATCH_TYPE_ALIASES.get(normalized)
    if alias is not None:
        return alias
    alias = MATCH_TYPE_ALIASES.get(value.strip())
    if alias is not None:
        return alias
    raise ValueError(f"unknown match type: {value}")


def match_type_choices() -> tuple[str, ...]:
    return tuple(SEASON2_MATCH_TYPES)


def get_match_type_rule(season: int, match_type: str) -> MatchTypeRule:
    key = normalize_match_type(match_type)
    if season != 2:
        raise ValueError(f"season {season} does not support match types yet")
    return SEASON2_MATCH_TYPES[key]


def build_group_round_two_start_grid(ranking: Sequence[int]) -> dict[int, tuple[int, ...]]:
    if len(ranking) != 6:
        raise ValueError("group round 2 seeding requires exactly 6 runners")
    ordered = tuple(ranking)
    return {
        -3: (ordered[5],),
        -2: (ordered[3], ordered[4]),
        -1: (ordered[1], ordered[2]),
        0: (ordered[0],),
    }


def format_start_spec_from_grid(start_grid: dict[int, Sequence[int]]) -> str:
    parts: list[str] = []
    for pos, runners in sorted(start_grid.items()):
        if not runners:
            continue
        parts.append(f"{pos}:{','.join(str(runner) for runner in runners)}")
    return ";".join(parts)


def build_group_round_two_start_spec(ranking: Sequence[int]) -> str:
    return format_start_spec_from_grid(build_group_round_two_start_grid(ranking))


def resolve_match_start_spec(rule: MatchTypeRule, runners: Sequence[int]) -> str:
    if rule.default_start is not None:
        return rule.default_start
    if rule.seeded_from_runner_order:
        return build_group_round_two_start_spec(runners)
    raise ValueError(f"match type {rule.key} does not have a default start layout")


def effective_qualify_cutoff(rule: MatchTypeRule, field_size: int) -> int:
    if field_size < 1:
        raise ValueError("field size must be at least 1")
    if rule.advancement_mode == ADVANCEMENT_ALL:
        return field_size
    if rule.advancement_mode == ADVANCEMENT_NONE:
        return 1
    if rule.qualify_cutoff is None:
        raise ValueError(f"match type {rule.key} is missing qualify_cutoff")
    return min(rule.qualify_cutoff, field_size)


def qualified_runners_for_rule(rule: MatchTypeRule, ranking: Sequence[int]) -> tuple[int, ...]:
    ordered = tuple(ranking)
    if rule.advancement_mode == ADVANCEMENT_ALL:
        return ordered
    if rule.advancement_mode == ADVANCEMENT_NONE:
        return ()
    if rule.qualify_cutoff is None:
        raise ValueError(f"match type {rule.key} is missing qualify_cutoff")
    return ordered[: min(rule.qualify_cutoff, len(ordered))]


def eliminated_runners_for_rule(rule: MatchTypeRule, ranking: Sequence[int]) -> tuple[int, ...]:
    ordered = tuple(ranking)
    if rule.advancement_mode != ADVANCEMENT_TOP_N:
        return ()
    if rule.qualify_cutoff is None:
        raise ValueError(f"match type {rule.key} is missing qualify_cutoff")
    return ordered[min(rule.qualify_cutoff, len(ordered)) :]
